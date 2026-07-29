package main

/*
#include <stdlib.h>
*/
import "C"
import (
	"compress/gzip"
	"encoding/json"
	"io"
	"os"

	"github.com/vmihailenco/msgpack/v5"
	"sunny-sailor/validator"
)

//export ValidateCandidatesFromFile
func ValidateCandidatesFromFile(dataPath, candPath, outPath *C.char) C.int {
	dp := C.GoString(dataPath)
	cp := C.GoString(candPath)
	op := C.GoString(outPath)

	candRaw, err := os.ReadFile(cp)
	if err != nil {
		return -1
	}
	var payload validator.InputPayload
	if err := msgpack.Unmarshal(candRaw, &payload.Candidates); err != nil {
		return -1
	}

	f, err := os.Open(dp)
	if err != nil {
		return -1
	}
	defer f.Close()
	gr, err := gzip.NewReader(f)
	if err != nil {
		return -1
	}
	raw, err := io.ReadAll(gr)
	gr.Close()
	if err != nil {
		return -1
	}
	if err := msgpack.Unmarshal(raw, &payload.Stocks); err != nil {
		return -1
	}

	results := validator.ValidateAllCandidates(payload)

	out, err := os.Create(op)
	if err != nil {
		return -1
	}
	defer out.Close()
	enc := json.NewEncoder(out)
	for _, r := range results {
		enc.Encode(r)
	}
	return C.int(len(results))
}

func main() {}
