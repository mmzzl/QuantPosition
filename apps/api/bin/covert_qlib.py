# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from systems.logs import Log
from systems.single import ScriptSingle
from systems.sys import home


if __name__ == "__main__":
    Log("covert_qlib", log_type=Log.TYPE_FILE, level=logging.INFO)
    pid_file = os.path.join(home(), "apps", "api", "var", "run", "covert_qlib.pid")
    single = ScriptSingle(pid_file)

    if single.is_running():
        logging.error("there is script lock {}".format(pid_file))
        sys.exit(0)

    cmd_path = os.path.join(home(), "apps", "api", "utils", "get_data.py")
    os.system(f"python {cmd_path} mongo mongo_to_csv --data_dir ~/.qlib/csv_data/mongo")
    os.system(f"python {cmd_path} mongo csv_to_qlib --data_path ~/.qlib/csv_data/mongo --qlib_dir ~/.qlib/qlib_data/cn_data")