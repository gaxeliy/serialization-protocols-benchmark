// Serialization benchmark — Go.
// Verifies protocol rankings from Python are not language-specific.
// Outputs JSON to results/go_results.json for plotting.

package main

import (
	"encoding/json"
	"fmt"
	"os"
	"runtime"
	"runtime/debug"
	"time"

	"github.com/vmihailenco/msgpack/v5"

	pb "github.com/gaxeliy/serialization-protocols-benchmark/go/generated"
	fb "github.com/gaxeliy/serialization-protocols-benchmark/go/generated/benchmark"

	flatbuffers "github.com/google/flatbuffers/go"

	"google.golang.org/protobuf/proto"
)

// ── data model (used by msgpack) ────────────────────────────────────────────

type SmallData struct {
	IntVal   int32   `msgpack:"int_val"`
	FloatVal float64 `msgpack:"float_val"`
	StrVal   string  `msgpack:"str_val"`
	BoolVal  bool    `msgpack:"bool_val"`
}

type Nested struct {
	IntVal   int32   `msgpack:"int_val"`
	FloatVal float64 `msgpack:"float_val"`
	StrVal   string  `msgpack:"str_val"`
	BoolVal  bool    `msgpack:"bool_val"`
}

type MediumData struct {
	Name     string            `msgpack:"name"`
	ID       int32             `msgpack:"id"`
	Scores   []float64         `msgpack:"scores"`
	Metadata map[string]string `msgpack:"metadata"`
	Nested   Nested            `msgpack:"nested"`
}

type ComplexItemData struct {
	Name  string   `msgpack:"name"`
	ID    int32    `msgpack:"id"`
	Score float64  `msgpack:"score"`
	Tags  []string `msgpack:"tags"`
}

type LargeData struct {
	Items []ComplexItemData `msgpack:"items"`
}

var (
	smallData = SmallData{IntVal: 42, FloatVal: 3.14, StrVal: "hello world", BoolVal: true}
	mediumData = MediumData{
		Name:     "test_object",
		ID:       12345,
		Scores:   []float64{1.0, 2.0, 3.0, 4.0, 5.0},
		Metadata: map[string]string{"key1": "value1", "key2": "value2", "key3": "value3"},
		Nested:   Nested{IntVal: 99, FloatVal: 2.71, StrVal: "nested", BoolVal: false},
	}
	largeData LargeData
)

func init() {
	items := make([]ComplexItemData, 100)
	for i := 0; i < 100; i++ {
		tags := make([]string, 5)
		for j := 0; j < 5; j++ {
			tags[j] = fmt.Sprintf("tag_%d", j)
		}
		items[i] = ComplexItemData{
			Name:  fmt.Sprintf("item_%04d", i),
			ID:    int32(i),
			Score: float64(i) * 1.5,
			Tags:  tags,
		}
	}
	largeData = LargeData{Items: items}
}

// ── ser/deser functions per protocol per dataset ────────────────────────────

// protobuf
func protoSerSmall() ([]byte, error) {
	msg := &pb.SmallMessage{IntVal: 42, FloatVal: 3.14, StrVal: "hello world", BoolVal: true}
	return proto.Marshal(msg)
}
func protoDeserSmall(data []byte) error {
	msg := &pb.SmallMessage{}
	if err := proto.Unmarshal(data, msg); err != nil {
		return err
	}
	_ = msg.IntVal + int32(msg.FloatVal) + int32(len(msg.StrVal))
	_ = msg.BoolVal
	return nil
}

func protoSerMedium() ([]byte, error) {
	msg := &pb.MediumMessage{
		Name:     "test_object",
		Id:       12345,
		Scores:   []float64{1.0, 2.0, 3.0, 4.0, 5.0},
		Metadata: map[string]string{"key1": "value1", "key2": "value2", "key3": "value3"},
		Nested:   &pb.PrimitiveTypes{IntVal: 99, FloatVal: 2.71, StrVal: "nested", BoolVal: false},
	}
	return proto.Marshal(msg)
}
func protoDeserMedium(data []byte) error {
	msg := &pb.MediumMessage{}
	if err := proto.Unmarshal(data, msg); err != nil {
		return err
	}
	_ = msg.Name + fmt.Sprint(msg.Id)
	for _, s := range msg.Scores {
		_ = s
	}
	for k, v := range msg.Metadata {
		_ = k + v
	}
	if msg.Nested != nil {
		_ = msg.Nested.IntVal + int32(msg.Nested.FloatVal)
		_ = msg.Nested.StrVal
		_ = msg.Nested.BoolVal
	}
	return nil
}

func protoSerLarge() ([]byte, error) {
	items := make([]*pb.ComplexItem, 100)
	for i := 0; i < 100; i++ {
		tags := make([]string, 5)
		for j := 0; j < 5; j++ {
			tags[j] = fmt.Sprintf("tag_%d", j)
		}
		items[i] = &pb.ComplexItem{
			Name:  fmt.Sprintf("item_%04d", i),
			Id:    int32(i),
			Score: float64(i) * 1.5,
			Tags:  tags,
		}
	}
	msg := &pb.LargeMessage{Items: items}
	return proto.Marshal(msg)
}
func protoDeserLarge(data []byte) error {
	msg := &pb.LargeMessage{}
	if err := proto.Unmarshal(data, msg); err != nil {
		return err
	}
	for _, item := range msg.Items {
		_ = item.Name
		_ = item.Id
		_ = item.Score
		for _, t := range item.Tags {
			_ = t
		}
	}
	return nil
}

// flatbuffers
func fbSerSmall() ([]byte, error) {
	b := flatbuffers.NewBuilder(128)
	s := b.CreateString("hello world")
	fb.SmallMessageStart(b)
	fb.SmallMessageAddIntVal(b, 42)
	fb.SmallMessageAddFloatVal(b, 3.14)
	fb.SmallMessageAddStrVal(b, s)
	fb.SmallMessageAddBoolVal(b, true)
	off := fb.SmallMessageEnd(b)
	b.Finish(off)
	return b.FinishedBytes(), nil
}
func fbDeserSmall(data []byte) error {
	msg := fb.GetRootAsSmallMessage(data, 0)
	_ = msg.IntVal()
	_ = msg.FloatVal()
	_ = msg.StrVal()
	_ = msg.BoolVal()
	return nil
}

func fbSerMedium() ([]byte, error) {
	b := flatbuffers.NewBuilder(2048)
	name := b.CreateString("test_object")

	// scores
	scores := []float64{1.0, 2.0, 3.0, 4.0, 5.0}
	fb.MediumMessageStartScoresVector(b, len(scores))
	for i := len(scores) - 1; i >= 0; i-- {
		b.PrependFloat64(scores[i])
	}
	scoresOff := b.EndVector(len(scores))

	// metadata keys & values
	mk := []string{"key1", "key2", "key3"}
	mv := []string{"value1", "value2", "value3"}
	keyOffs := make([]flatbuffers.UOffsetT, len(mk))
	valOffs := make([]flatbuffers.UOffsetT, len(mv))
	for i := range mk {
		keyOffs[i] = b.CreateString(mk[i])
		valOffs[i] = b.CreateString(mv[i])
	}
	fb.MediumMessageStartMetadataValuesVector(b, len(valOffs))
	for i := len(valOffs) - 1; i >= 0; i-- {
		b.PrependUOffsetT(valOffs[i])
	}
	valsOff := b.EndVector(len(valOffs))
	fb.MediumMessageStartMetadataKeysVector(b, len(keyOffs))
	for i := len(keyOffs) - 1; i >= 0; i-- {
		b.PrependUOffsetT(keyOffs[i])
	}
	keysOff := b.EndVector(len(keyOffs))

	// nested
	nStr := b.CreateString("nested")
	fb.PrimitiveTypesStart(b)
	fb.PrimitiveTypesAddIntVal(b, 99)
	fb.PrimitiveTypesAddFloatVal(b, 2.71)
	fb.PrimitiveTypesAddStrVal(b, nStr)
	fb.PrimitiveTypesAddBoolVal(b, false)
	nestedOff := fb.PrimitiveTypesEnd(b)

	fb.MediumMessageStart(b)
	fb.MediumMessageAddName(b, name)
	fb.MediumMessageAddId(b, 12345)
	fb.MediumMessageAddScores(b, scoresOff)
	fb.MediumMessageAddMetadataKeys(b, keysOff)
	fb.MediumMessageAddMetadataValues(b, valsOff)
	fb.MediumMessageAddNested(b, nestedOff)
	off := fb.MediumMessageEnd(b)
	b.Finish(off)
	return b.FinishedBytes(), nil
}
func fbDeserMedium(data []byte) error {
	msg := fb.GetRootAsMediumMessage(data, 0)
	_ = string(msg.Name())
	_ = msg.Id()
	for i := 0; i < msg.ScoresLength(); i++ {
		_ = msg.Scores(i)
	}
	for i := 0; i < msg.MetadataKeysLength(); i++ {
		_ = string(msg.MetadataKeys(i))
		_ = string(msg.MetadataValues(i))
	}
	n := msg.Nested(new(fb.PrimitiveTypes))
	if n != nil {
		_ = n.IntVal()
		_ = n.FloatVal()
		_ = n.StrVal()
		_ = n.BoolVal()
	}
	return nil
}

func fbSerLarge() ([]byte, error) {
	b := flatbuffers.NewBuilder(65536)
	itemOffs := make([]flatbuffers.UOffsetT, 100)
	for i := 0; i < 100; i++ {
		name := b.CreateString(fmt.Sprintf("item_%04d", i))
		tagStrs := make([]flatbuffers.UOffsetT, 5)
		for j := 0; j < 5; j++ {
			tagStrs[j] = b.CreateString(fmt.Sprintf("tag_%d", j))
		}
		fb.ComplexItemStartTagsVector(b, len(tagStrs))
		for j := len(tagStrs) - 1; j >= 0; j-- {
			b.PrependUOffsetT(tagStrs[j])
		}
		tagsOff := b.EndVector(len(tagStrs))
		fb.ComplexItemStart(b)
		fb.ComplexItemAddName(b, name)
		fb.ComplexItemAddId(b, int32(i))
		fb.ComplexItemAddScore(b, float64(i)*1.5)
		fb.ComplexItemAddTags(b, tagsOff)
		itemOffs[i] = fb.ComplexItemEnd(b)
	}
	fb.LargeMessageStartItemsVector(b, len(itemOffs))
	for i := len(itemOffs) - 1; i >= 0; i-- {
		b.PrependUOffsetT(itemOffs[i])
	}
	itemsOff := b.EndVector(len(itemOffs))
	fb.LargeMessageStart(b)
	fb.LargeMessageAddItems(b, itemsOff)
	off := fb.LargeMessageEnd(b)
	b.Finish(off)
	return b.FinishedBytes(), nil
}
func fbDeserLarge(data []byte) error {
	msg := fb.GetRootAsLargeMessage(data, 0)
	for i := 0; i < msg.ItemsLength(); i++ {
		item := new(fb.ComplexItem)
		msg.Items(item, i)
		_ = string(item.Name())
		_ = item.Id()
		_ = item.Score()
		for j := 0; j < item.TagsLength(); j++ {
			_ = string(item.Tags(j))
		}
	}
	return nil
}

// flatbuffers — builder reuse

var (
	fbBuilderSmall  = flatbuffers.NewBuilder(128)
	fbBuilderMedium = flatbuffers.NewBuilder(2048)
	fbBuilderLarge  = flatbuffers.NewBuilder(65536)
)

func fbReuseSerSmall() ([]byte, error) {
	b := fbBuilderSmall
	b.Reset()
	s := b.CreateString("hello world")
	fb.SmallMessageStart(b)
	fb.SmallMessageAddIntVal(b, 42)
	fb.SmallMessageAddFloatVal(b, 3.14)
	fb.SmallMessageAddStrVal(b, s)
	fb.SmallMessageAddBoolVal(b, true)
	off := fb.SmallMessageEnd(b)
	b.Finish(off)
	return b.FinishedBytes(), nil
}

func fbReuseSerMedium() ([]byte, error) {
	b := fbBuilderMedium
	b.Reset()
	name := b.CreateString("test_object")
	scores := []float64{1.0, 2.0, 3.0, 4.0, 5.0}
	fb.MediumMessageStartScoresVector(b, len(scores))
	for i := len(scores) - 1; i >= 0; i-- {
		b.PrependFloat64(scores[i])
	}
	scoresOff := b.EndVector(len(scores))
	mk := []string{"key1", "key2", "key3"}
	mv := []string{"value1", "value2", "value3"}
	keyOffs := make([]flatbuffers.UOffsetT, len(mk))
	valOffs := make([]flatbuffers.UOffsetT, len(mv))
	for i := range mk {
		keyOffs[i] = b.CreateString(mk[i])
		valOffs[i] = b.CreateString(mv[i])
	}
	fb.MediumMessageStartMetadataValuesVector(b, len(valOffs))
	for i := len(valOffs) - 1; i >= 0; i-- {
		b.PrependUOffsetT(valOffs[i])
	}
	valsOff := b.EndVector(len(valOffs))
	fb.MediumMessageStartMetadataKeysVector(b, len(keyOffs))
	for i := len(keyOffs) - 1; i >= 0; i-- {
		b.PrependUOffsetT(keyOffs[i])
	}
	keysOff := b.EndVector(len(keyOffs))
	nStr := b.CreateString("nested")
	fb.PrimitiveTypesStart(b)
	fb.PrimitiveTypesAddIntVal(b, 99)
	fb.PrimitiveTypesAddFloatVal(b, 2.71)
	fb.PrimitiveTypesAddStrVal(b, nStr)
	fb.PrimitiveTypesAddBoolVal(b, false)
	nestedOff := fb.PrimitiveTypesEnd(b)
	fb.MediumMessageStart(b)
	fb.MediumMessageAddName(b, name)
	fb.MediumMessageAddId(b, 12345)
	fb.MediumMessageAddScores(b, scoresOff)
	fb.MediumMessageAddMetadataKeys(b, keysOff)
	fb.MediumMessageAddMetadataValues(b, valsOff)
	fb.MediumMessageAddNested(b, nestedOff)
	off := fb.MediumMessageEnd(b)
	b.Finish(off)
	return b.FinishedBytes(), nil
}

func fbReuseSerLarge() ([]byte, error) {
	b := fbBuilderLarge
	b.Reset()
	itemOffs := make([]flatbuffers.UOffsetT, 100)
	for i := 0; i < 100; i++ {
		name := b.CreateString(fmt.Sprintf("item_%04d", i))
		tagStrs := make([]flatbuffers.UOffsetT, 5)
		for j := 0; j < 5; j++ {
			tagStrs[j] = b.CreateString(fmt.Sprintf("tag_%d", j))
		}
		fb.ComplexItemStartTagsVector(b, len(tagStrs))
		for j := len(tagStrs) - 1; j >= 0; j-- {
			b.PrependUOffsetT(tagStrs[j])
		}
		tagsOff := b.EndVector(len(tagStrs))
		fb.ComplexItemStart(b)
		fb.ComplexItemAddName(b, name)
		fb.ComplexItemAddId(b, int32(i))
		fb.ComplexItemAddScore(b, float64(i)*1.5)
		fb.ComplexItemAddTags(b, tagsOff)
		itemOffs[i] = fb.ComplexItemEnd(b)
	}
	fb.LargeMessageStartItemsVector(b, len(itemOffs))
	for i := len(itemOffs) - 1; i >= 0; i-- {
		b.PrependUOffsetT(itemOffs[i])
	}
	itemsOff := b.EndVector(len(itemOffs))
	fb.LargeMessageStart(b)
	fb.LargeMessageAddItems(b, itemsOff)
	off := fb.LargeMessageEnd(b)
	b.Finish(off)
	return b.FinishedBytes(), nil
}

// msgpack
func mpSerSmall() ([]byte, error)   { return msgpack.Marshal(smallData) }
func mpDeserSmall(d []byte) error   { var v SmallData; return msgpack.Unmarshal(d, &v) }
func mpSerMedium() ([]byte, error)  { return msgpack.Marshal(mediumData) }
func mpDeserMedium(d []byte) error  { var v MediumData; return msgpack.Unmarshal(d, &v) }
func mpSerLarge() ([]byte, error)   { return msgpack.Marshal(largeData) }
func mpDeserLarge(d []byte) error   { var v LargeData; return msgpack.Unmarshal(d, &v) }

// ── benchmark runner ────────────────────────────────────────────────────────

type serFunc func() ([]byte, error)
type deserFunc func([]byte) error

type BenchmarkResult struct {
	Language          string  `json:"language"`
	Protocol          string  `json:"protocol"`
	Dataset           string  `json:"dataset"`
	SizeBytes         int     `json:"size_bytes"`
	SerializationTime float64 `json:"serialization_time_us"`
	DeserializationTime float64 `json:"deserialization_time_us"`
}

func runBench(protocol, dataset string, ser serFunc, des deserFunc, iters int) BenchmarkResult {
	// warmup
	for i := 0; i < 200; i++ {
		d, err := ser()
		if err != nil {
			panic(fmt.Sprintf("ser warmup: %v", err))
		}
		if err := des(d); err != nil {
			panic(fmt.Sprintf("des warmup: %v", err))
		}
	}

	// size
	d, err := ser()
	if err != nil {
		panic(fmt.Sprintf("ser size: %v", err))
	}
	sz := len(d)

	// disable GC during timed loops for stable measurements
	origGC := debug.SetGCPercent(-1)
	defer debug.SetGCPercent(origGC)

	// ser time
	t0 := time.Now()
	for i := 0; i < iters; i++ {
		if _, err := ser(); err != nil {
			panic(fmt.Sprintf("ser loop: %v", err))
		}
	}
	serUs := float64(time.Since(t0).Nanoseconds()) / float64(iters) / 1000.0

	// collect garbage from ser loop before deser measurement
	runtime.GC()

	// deser time
	t0 = time.Now()
	for i := 0; i < iters; i++ {
		if err := des(d); err != nil {
			panic(fmt.Sprintf("des loop: %v", err))
		}
	}
	deserUs := float64(time.Since(t0).Nanoseconds()) / float64(iters) / 1000.0

	return BenchmarkResult{
		Language:           "go",
		Protocol:           protocol,
		Dataset:            dataset,
		SizeBytes:          sz,
		SerializationTime:  serUs,
		DeserializationTime: deserUs,
	}
}

// ── main ────────────────────────────────────────────────────────────────────

func main() {
	os.MkdirAll("../results", 0o755)

	type protoEntry struct {
		name string
		ser  serFunc
		des  deserFunc
	}

	protocols := map[string]map[string]protoEntry{
		"protobuf": {
			"small":  {"protobuf_small", protoSerSmall, protoDeserSmall},
			"medium": {"protobuf_medium", protoSerMedium, protoDeserMedium},
			"large":  {"protobuf_large", protoSerLarge, protoDeserLarge},
		},
		"flatbuffers": {
			"small":  {"flatbuffers_small", fbSerSmall, fbDeserSmall},
			"medium": {"flatbuffers_medium", fbSerMedium, fbDeserMedium},
			"large":  {"flatbuffers_large", fbSerLarge, fbDeserLarge},
		},
		"flatbuffers-reuse": {
			"small":  {"flatbuffers_reuse_small", fbReuseSerSmall, fbDeserSmall},
			"medium": {"flatbuffers_reuse_medium", fbReuseSerMedium, fbDeserMedium},
			"large":  {"flatbuffers_reuse_large", fbReuseSerLarge, fbDeserLarge},
		},
		"msgpack": {
			"small":  {"msgpack_small", mpSerSmall, mpDeserSmall},
			"medium": {"msgpack_medium", mpSerMedium, mpDeserMedium},
			"large":  {"msgpack_large", mpSerLarge, mpDeserLarge},
		},
	}

	var results []BenchmarkResult

	for protoName, datasets := range protocols {
		for dsName, entry := range datasets {
			iters := 10000
			if dsName == "large" {
				iters = 2000
			}
			r := runBench(protoName, dsName, entry.ser, entry.des, iters)
			results = append(results, r)
			fmt.Printf("[%-12s] %-6s  size=%-6d B  ser=%-10.2f us  des=%-10.2f us\n",
				protoName, dsName, r.SizeBytes, r.SerializationTime, r.DeserializationTime)
		}
	}

	out, err := json.MarshalIndent(results, "", "  ")
	if err != nil {
		panic(err)
	}
	outPath := "../results/go_results.json"
	if err := os.WriteFile(outPath, out, 0o644); err != nil {
		panic(err)
	}
	fmt.Printf("\nResults written to %s\n", outPath)
}
