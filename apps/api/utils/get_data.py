# -*- coding: utf-8 -*-

import logging
import sys
import fire
import traceback
from tqdm import tqdm
import pandas as pd
from typing import Any, Dict, List, Optional
from pathlib import Path
from functools import partial

from pymongo import ASCENDING
from qlib.tests.data import GetData
from qlib.utils import fname_to_code
from dump_bin import DumpDataUpdate as _DumpDataUpdate, DumpDataFix, DumpDataAll
from concurrent.futures import ThreadPoolExecutor, as_completed
from database import get_db


class _DumpDataUpdateSafe(_DumpDataUpdate):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 确保 _update_instruments 的所有 key 为字符串
        self._update_instruments = {
            str(k): v for k, v in self._update_instruments.items()
        }

    def _dump_features(self):
        error_code = {}
        _dump_func = partial(
            self._dump_bin, calendar_list=self._new_calendar_list)
        with ThreadPoolExecutor(max_workers=self.works) as executor:
            futures = {}
            for _code, _df in self._all_data.groupby(self.symbol_field_name, group_keys=False):
                _code = fname_to_code(str(_code).lower()).upper()
                _start, _end = self._get_date(_df, is_begin_end=True)
                if not (isinstance(_start, pd.Timestamp) and isinstance(_end, pd.Timestamp)):
                    continue
                if _code in self._update_instruments:
                    _update_calendars = (
                        _df[_df[self.date_field_name] >
                            self._update_instruments[_code][self.INSTRUMENTS_END_FIELD]]
                        [self.date_field_name].sort_values().to_list()
                    )
                    if _update_calendars:
                        self._update_instruments[_code][self.INSTRUMENTS_END_FIELD] = self._format_datetime(
                            _end)
                        futures[executor.submit(
                            _dump_func, _df, _update_calendars)] = _code
                else:
                    _dt_range = self._update_instruments.setdefault(
                        _code, dict())
                    _dt_range[self.INSTRUMENTS_START_FIELD] = self._format_datetime(
                        _start)
                    _dt_range[self.INSTRUMENTS_END_FIELD] = self._format_datetime(
                        _end)
                    futures[executor.submit(
                        _dump_func, _df, self._new_calendar_list)] = _code
            with tqdm(total=len(futures)) as p_bar:
                for _future in as_completed(futures):
                    try:
                        _future.result()
                    except Exception:
                        error_code[futures[_future]] = traceback.format_exc()
                    p_bar.update()

    def dump(self):
        self.save_calendars(self._new_calendar_list)
        self._dump_features()
        df = pd.DataFrame.from_dict(self._update_instruments, orient="index")
        df.index.names = [self.symbol_field_name]
        df = df.reset_index()
        df[self.symbol_field_name] = df[self.symbol_field_name].astype(str)
        self.save_instruments(df)


class GetDataFromMongo(GetData):
    """从MongoDB读取K线数据并转为Qlib格式。

   继承 GetData 保留远程下载能力，新增 MongoDB K线 查询/导出 功能。

   Examples
   ---------
   # 查询单只股票K线
   python get_data.py mongo_kline --code 000001 --limit 5

   # 导出全部K线到Qlib二进制格式（增量同步）
   python get_data.py mongo_to_qlib --target_dir ~/.qlib/qlib_data/cn_data

   # 导出全部K线到Qlib二进制格式（全量重建）
   python get_data.py mongo_to_qlib --target_dir ~/.qlib/qlib_data/cn_data --mode full

   # 仅限特定股票
   python get_data.py mongo_to_qlib --instruments 600519,000001
   -------
   """

    def __init__(self, delete_zip_file=False):
        super().__init__(delete_zip_file)
        self.db = get_db()
        self.storage = self.db['stock_kline']

    def get_kline(self, code: str, start_date: str = None, end_date: str = None, limit: int = 100):
        query = {"code": code}
        if start_date:
            query["date"] = {"$gte": start_date}
        if end_date:
            query.setdefault("date", {})["$lte"] = end_date
        cursor = self.storage.find(query, {"_id": 0}).sort(
            "date", -1).limit(limit)
        results = []
        for doc in cursor:
            results.append(doc)
        return results

    def mongo_to_csv(
        self,
        data_dir: str = "~/.qlib/csv_data/mongo",
        instruments: Optional[str] = None,
        date_field_name: str = "date",
        incremental: bool = True,
    ) -> int:
        """将MongoDB中全部K线数据批量导出为CSV文件，每只股票一个文件

        Parameters
        ----------
        data_dir : str
            CSV输出目录，每只股票存为 {code}.csv
        instruments : str, optional
            逗号分隔的股票代码，不指定则导出全部
        date_field_name : str, default "date"
            日期字段名
        incremental : bool, default True
            增量模式：已有CSV时只追加新数据，避免重复导出

        Returns
        -------
        int
            导出的文件数

        Examples
        ---------
        # 首次全量导出
        python get_data.py mongo mongo_to_csv --data_dir ~/.qlib/csv_data/mongo

        # 后续增量追加
        python get_data.py mongo mongo_to_csv --data_dir ~/.qlib/csv_data/mongo

        # 强制全量重导
        python get_data.py mongo mongo_to_csv \\
            --data_dir ~/.qlib/csv_data/mongo --incremental false

        # 导出后直接转Qlib bin
        python get_data.py mongo csv_to_qlib \\
            --data_path ~/.qlib/csv_data/mongo --qlib_dir ~/.qlib/qlib_data/cn_data
        -------
        """
        data_dir = Path(data_dir).expanduser()
        data_dir.mkdir(parents=True, exist_ok=True)
        try:
            # 确定要导出的股票列表
            if instruments:
                codes = [c.strip()
                         for c in instruments.split(",") if c.strip()]
            else:
                pipeline = [{"$group": {"_id": "$code"}},
                            {"$sort": {"_id": ASCENDING}}]
                codes = [r["_id"] for r in self.storage.aggregate(pipeline)]

            exported = 0
            skipped = 0
            for code in tqdm(codes, desc="导出股票"):
                csv_path = data_dir / f"{code}.csv"

                # 增量模式：检查已有CSV的最后日期
                last_date = None
                if incremental and csv_path.exists():
                    try:
                        existing = pd.read_csv(csv_path)
                        if date_field_name in existing.columns and not existing.empty:
                            existing[date_field_name] = pd.to_datetime(
                                existing[date_field_name])
                            last_date = existing[date_field_name].max()
                    except Exception:
                        pass

                # 按 last_date 过滤查询
                query = {"code": code}
                if last_date is not None:
                    query["date"] = {"$gt": last_date.strftime("%Y-%m-%d")}

                docs = list(self.storage.find(
                    query,
                    {"_id": 0, "crawl_time": 0, "adjust": 0, "frequency": 0},
                ).sort("date", ASCENDING))
                if not docs:
                    if last_date is None:
                        skipped += 1
                    continue

                df = pd.DataFrame(docs)
                if date_field_name in df.columns:
                    df[date_field_name] = pd.to_datetime(
                        df[date_field_name]).dt.strftime("%Y-%m-%d")

                # 固定列顺序，确保追加时与已有CSV对齐
                kline_fields = ["code", "date", "open",
                                "high", "low", "close", "volume", "amount"]
                df = df[[c for c in kline_fields if c in df.columns]]

                # 追加或新建
                if incremental and csv_path.exists() and last_date is not None:
                    df.to_csv(csv_path, mode="a", header=False,
                              index=False, encoding="utf-8")
                else:
                    df = df.sort_values(date_field_name)
                    df.to_csv(csv_path, index=False, encoding="utf-8")
                exported += 1

            action = "增量" if incremental else "全量"
            logging.info(
                f"MongoDB -> CSV {action}导出完成: {exported} 只股票更新, {skipped} 只无数据, 目录: {data_dir}")
            return exported
        except Exception:
            raise

    def csv_to_qlib(
        self,
        data_path: str,
        qlib_dir: str = "~/.qlib/qlib_data/cn_data",
        mode: str = "full",
        freq: str = "day",
        date_field_name: str = "date",
        symbol_field_name: str = "symbol",
        include_fields: str = "",
        exclude_fields: str = "",
        max_workers: int = 16,
        limit_nums: int = None,
    ) -> None:
        """将CSV数据目录转换为Qlib二进制格式

        Parameters
        ----------
        data_path : str
            CSV数据文件或目录路径
        qlib_dir : str
            Qlib输出目录
        mode : str, default "full"
            转换模式: full(全量重建) / incremental(增量追加) / fix(补充新股票)
        freq : str, default "day"
            数据频率
        date_field_name : str, default "date"
            日期字段名，MongoDB导出为 "date"
        symbol_field_name : str, default "symbol"
            股票代码字段名
        include_fields : str
            逗号分隔的要导出的字段，为空则导出全部（除 exclude_fields）
        exclude_fields : str
            逗号分隔的要排除的字段
        max_workers : int, default 16
            并发线程数
        limit_nums : int
            限制处理的文件数（调试用）

        Examples
        ---------
        # 首次全量重建
        python get_data.py mongo csv_to_qlib \\
            --data_path ~/.qlib/csv_data/mongo \\
            --qlib_dir ~/.qlib/qlib_data/cn_data

        # 后续增量追加（只更新已有bin）
        python get_data.py mongo csv_to_qlib \\
            --data_path ~/.qlib/csv_data/mongo \\
            --qlib_dir ~/.qlib/qlib_data/cn_data --mode incremental

        # 补充新股票到已有数据集
        python get_data.py mongo csv_to_qlib \\
            --data_path ~/.qlib/csv_data/mongo \\
            --qlib_dir ~/.qlib/qlib_data/cn_data --mode fix
        -------
        """
        if mode == "incremental":
            # Windows 上 ProcessPoolExecutor 传大 DataFrame 会导致 MemoryError，
            # 用 ThreadPoolExecutor 替代（I/O 密集型，无 pickle 开销）
            dumper = _DumpDataUpdateSafe(
                data_path=data_path,
                qlib_dir=qlib_dir,
                freq=freq,
                date_field_name=date_field_name,
                symbol_field_name=symbol_field_name,
                include_fields=include_fields,
                exclude_fields=exclude_fields,
                max_workers=max_workers,
                limit_nums=limit_nums,
            )
        elif mode == "fix":
            dumper = DumpDataFix(
                data_path=data_path,
                qlib_dir=qlib_dir,
                freq=freq,
                date_field_name=date_field_name,
                symbol_field_name=symbol_field_name,
                include_fields=include_fields,
                exclude_fields=exclude_fields,
                max_workers=max_workers,
                limit_nums=limit_nums,
            )
        else:
            dumper = DumpDataAll(
                data_path=data_path,
                qlib_dir=qlib_dir,
                freq=freq,
                date_field_name=date_field_name,
                symbol_field_name=symbol_field_name,
                include_fields=include_fields,
                exclude_fields=exclude_fields,
                max_workers=max_workers,
                limit_nums=limit_nums,
            )
        dumper.dump()
        logging.info(f"CSV -> Qlib 转换完成（{mode}模式），输出目录: {qlib_dir}")
        self._generate_pool_files(qlib_dir)

    def _generate_pool_files(self, qlib_dir: str) -> None:
        """根据 all.txt 和 hs300/zz500 配置生成池文件"""
        qlib_dir = Path(qlib_dir).expanduser()
        all_txt = qlib_dir / "instruments" / "all.txt"
        if not all_txt.exists():
            logging.warning(f"all.txt 不存在，跳过池文件生成: {all_txt}")
            return

        # 读取 all.txt -> {code: (start, end)}
        # 代码格式与 CSV 一致（如 000001，不带 SH/SZ 前缀）
        inst_map = {}
        with open(all_txt, encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) == 3:
                    inst_map[parts[0]] = (parts[1], parts[2])

        data_dir = Path(__file__).resolve().parent.parent.parent / "data"
        for pool_name in ("hs300", "zz500"):
            csv_file = data_dir / f"{pool_name}_stocks.csv"
            pool_file = qlib_dir / "instruments" / f"{pool_name}.txt"
            entries = []
            if csv_file.exists():
                df = pd.read_csv(csv_file)
                for _, row in df.iterrows():
                    code = str(row.get("code", "")).strip().zfill(6)
                    if not code:
                        continue
                    # all.txt 使用原始代码（不带 SH/SZ 前缀），直接匹配
                    if code in inst_map:
                        s, e = inst_map[code]
                        entries.append((code, s, e))
            entries.sort(key=lambda x: x[0])
            pool_file.parent.mkdir(parents=True, exist_ok=True)
            with open(pool_file, "w", encoding="utf-8") as f:
                for inst, s, e in entries:
                    f.write(f"{inst}\t{s}\t{e}\n")
            logging.info(f"生成 {pool_file} ({len(entries)} 只)")


if __name__ == "__main__":
    fire.Fire({"download": GetData, "mongo": GetDataFromMongo})
