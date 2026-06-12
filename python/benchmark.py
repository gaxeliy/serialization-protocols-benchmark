"""Serialization benchmark — Python.

Compares protobuf, flatbuffers, msgpack, and pickle across
small / medium / large payloads.
Outputs results to results/python_results.json for plotting.
"""

import gc
import json
import pickle
import time
import sys
import os

import msgpack

# ── generated code ──
_here = os.path.dirname(__file__)
sys.path.insert(0, _here)                       # so "from generated import ..." works
sys.path.insert(0, os.path.join(_here, "generated"))  # flatbuffers code expects "benchmark" top-level
from generated import benchmark_pb2  # type: ignore
from generated.benchmark import (     # type: ignore
    SmallMessage,
    MediumMessage,
    LargeMessage,
    ComplexItem,
    PrimitiveTypes,
    # Builder helpers
    SmallMessageStart, SmallMessageAddIntVal, SmallMessageAddFloatVal,
    SmallMessageAddStrVal, SmallMessageAddBoolVal, SmallMessageEnd,
    MediumMessageStart, MediumMessageAddName, MediumMessageAddId,
    MediumMessageAddScores, MediumMessageStartScoresVector,
    MediumMessageAddMetadataKeys, MediumMessageStartMetadataKeysVector,
    MediumMessageAddMetadataValues, MediumMessageStartMetadataValuesVector,
    MediumMessageAddNested, MediumMessageEnd,
    LargeMessageStart, LargeMessageAddItems, LargeMessageStartItemsVector,
    LargeMessageEnd,
    ComplexItemStart, ComplexItemAddName, ComplexItemAddId,
    ComplexItemAddScore, ComplexItemAddTags, ComplexItemStartTagsVector,
    ComplexItemEnd,
    PrimitiveTypesStart, PrimitiveTypesAddIntVal, PrimitiveTypesAddFloatVal,
    PrimitiveTypesAddStrVal, PrimitiveTypesAddBoolVal, PrimitiveTypesEnd,
)
import flatbuffers


# =============================================================================
# Test data  (plain Python dicts used by msgpack & pickle)
# =============================================================================

small_data = {
    "int_val": 42,
    "float_val": 3.14,
    "str_val": "hello world",
    "bool_val": True,
}

medium_data = {
    "name": "test_object",
    "id": 12345,
    "scores": [1.0, 2.0, 3.0, 4.0, 5.0],
    "metadata": {"key1": "value1", "key2": "value2", "key3": "value3"},
    "nested": {"int_val": 99, "float_val": 2.71, "str_val": "nested", "bool_val": False},
}

large_data = {
    "items": [
        {
            "name": f"item_{i:04d}",
            "id": i,
            "score": i * 1.5,
            "tags": [f"tag_{j}" for j in range(5)],
        }
        for i in range(100)
    ],
}


# =============================================================================
# Serialize / deserialize helpers per protocol per data-set
# =============================================================================

# ── protobuf ─────────────────────────────────────────────────────────────────

def _proto_serialize_small():
    msg = benchmark_pb2.SmallMessage(int_val=42, float_val=3.14, str_val="hello world", bool_val=True)
    return msg.SerializeToString()


def _proto_deserialize_small(data: bytes):
    msg = benchmark_pb2.SmallMessage()
    msg.ParseFromString(data)
    _ = (msg.int_val, msg.float_val, msg.str_val, msg.bool_val)


def _proto_serialize_medium():
    msg = benchmark_pb2.MediumMessage(
        name="test_object",
        id=12345,
        scores=[1.0, 2.0, 3.0, 4.0, 5.0],
        metadata={"key1": "value1", "key2": "value2", "key3": "value3"},
        nested=benchmark_pb2.PrimitiveTypes(int_val=99, float_val=2.71, str_val="nested", bool_val=False),
    )
    return msg.SerializeToString()


def _proto_deserialize_medium(data: bytes):
    msg = benchmark_pb2.MediumMessage()
    msg.ParseFromString(data)
    _ = (msg.name, msg.id)
    for s in msg.scores:
        _ = s
    for k, v in msg.metadata.items():
        _ = (k, v)
    _ = (msg.nested.int_val, msg.nested.float_val, msg.nested.str_val, msg.nested.bool_val)


def _proto_serialize_large():
    items = []
    for i in range(100):
        items.append(benchmark_pb2.ComplexItem(
            name=f"item_{i:04d}", id=i, score=i * 1.5,
            tags=[f"tag_{j}" for j in range(5)],
        ))
    msg = benchmark_pb2.LargeMessage(items=items)
    return msg.SerializeToString()


def _proto_deserialize_large(data: bytes):
    msg = benchmark_pb2.LargeMessage()
    msg.ParseFromString(data)
    for item in msg.items:
        _ = (item.name, item.id, item.score)
        for t in item.tags:
            _ = t


# ── flatbuffers ──────────────────────────────────────────────────────────────

def _fb_serialize_small():
    b = flatbuffers.Builder(128)
    s = b.CreateString("hello world")
    SmallMessageStart(b)
    SmallMessageAddIntVal(b, 42)
    SmallMessageAddFloatVal(b, 3.14)
    SmallMessageAddStrVal(b, s)
    SmallMessageAddBoolVal(b, True)
    off = SmallMessageEnd(b)
    b.Finish(off)
    return b.Output()


def _fb_deserialize_small(data: bytes):
    msg = SmallMessage.GetRootAs(data, 0)
    _ = (msg.IntVal(), msg.FloatVal(), msg.StrVal(), msg.BoolVal())


def _fb_serialize_medium():
    b = flatbuffers.Builder(1024)
    name = b.CreateString("test_object")

    # scores vector
    scores = [1.0, 2.0, 3.0, 4.0, 5.0]
    MediumMessageStartScoresVector(b, len(scores))
    for v in reversed(scores):
        b.PrependFloat64(v)
    scores_off = b.EndVector()

    # metadata (parallel key/value arrays)
    m_keys = ["key1", "key2", "key3"]
    m_vals = ["value1", "value2", "value3"]
    key_offsets = [b.CreateString(k) for k in m_keys]
    val_offsets = [b.CreateString(v) for v in m_vals]
    MediumMessageStartMetadataValuesVector(b, len(val_offsets))
    for off in reversed(val_offsets):
        b.PrependUOffsetTRelative(off)
    vals_off = b.EndVector()
    MediumMessageStartMetadataKeysVector(b, len(key_offsets))
    for off in reversed(key_offsets):
        b.PrependUOffsetTRelative(off)
    keys_off = b.EndVector()

    # nested PrimitiveTypes
    n_str = b.CreateString("nested")
    PrimitiveTypesStart(b)
    PrimitiveTypesAddIntVal(b, 99)
    PrimitiveTypesAddFloatVal(b, 2.71)
    PrimitiveTypesAddStrVal(b, n_str)
    PrimitiveTypesAddBoolVal(b, False)
    nested_off = PrimitiveTypesEnd(b)

    MediumMessageStart(b)
    MediumMessageAddName(b, name)
    MediumMessageAddId(b, 12345)
    MediumMessageAddScores(b, scores_off)
    MediumMessageAddMetadataKeys(b, keys_off)
    MediumMessageAddMetadataValues(b, vals_off)
    MediumMessageAddNested(b, nested_off)
    off = MediumMessageEnd(b)
    b.Finish(off)
    return b.Output()


def _fb_deserialize_medium(data: bytes):
    msg = MediumMessage.GetRootAs(data, 0)
    _ = msg.Name()
    _ = msg.Id()
    for i in range(msg.ScoresLength()):
        _ = msg.Scores(i)
    for i in range(msg.MetadataKeysLength()):
        _ = (msg.MetadataKeys(i), msg.MetadataValues(i))
    nested = msg.Nested()
    if nested:
        _ = (nested.IntVal(), nested.FloatVal(), nested.StrVal(), nested.BoolVal())


def _fb_serialize_large():
    b = flatbuffers.Builder(32768)
    item_offsets = []
    for i in range(100):
        name = b.CreateString(f"item_{i:04d}")
        tag_strs = [b.CreateString(f"tag_{j}") for j in range(5)]
        ComplexItemStartTagsVector(b, len(tag_strs))
        for ts in reversed(tag_strs):
            b.PrependUOffsetTRelative(ts)
        tags_off = b.EndVector()
        ComplexItemStart(b)
        ComplexItemAddName(b, name)
        ComplexItemAddId(b, i)
        ComplexItemAddScore(b, i * 1.5)
        ComplexItemAddTags(b, tags_off)
        item_offsets.append(ComplexItemEnd(b))

    LargeMessageStartItemsVector(b, len(item_offsets))
    for off in reversed(item_offsets):
        b.PrependUOffsetTRelative(off)
    items_off = b.EndVector()

    LargeMessageStart(b)
    LargeMessageAddItems(b, items_off)
    off = LargeMessageEnd(b)
    b.Finish(off)
    return b.Output()


def _fb_deserialize_large(data: bytes):
    msg = LargeMessage.GetRootAs(data, 0)
    for i in range(msg.ItemsLength()):
        item = msg.Items(i)
        _ = item.Name()
        _ = item.Id()
        _ = item.Score()
        for j in range(item.TagsLength()):
            _ = item.Tags(j)


# ── flatbuffers (builder reuse) ──────────────────────────────────────────────

_fb_builder_small = flatbuffers.Builder(128)
_fb_builder_medium = flatbuffers.Builder(1024)
_fb_builder_large = flatbuffers.Builder(32768)


def _fb_reuse_serialize_small():
    b = _fb_builder_small
    b.Clear()
    s = b.CreateString("hello world")
    SmallMessageStart(b)
    SmallMessageAddIntVal(b, 42)
    SmallMessageAddFloatVal(b, 3.14)
    SmallMessageAddStrVal(b, s)
    SmallMessageAddBoolVal(b, True)
    off = SmallMessageEnd(b)
    b.Finish(off)
    return b.Output()


def _fb_reuse_serialize_medium():
    b = _fb_builder_medium
    b.Clear()
    name = b.CreateString("test_object")
    scores = [1.0, 2.0, 3.0, 4.0, 5.0]
    MediumMessageStartScoresVector(b, len(scores))
    for v in reversed(scores):
        b.PrependFloat64(v)
    scores_off = b.EndVector()
    m_keys = ["key1", "key2", "key3"]
    m_vals = ["value1", "value2", "value3"]
    key_offsets = [b.CreateString(k) for k in m_keys]
    val_offsets = [b.CreateString(v) for v in m_vals]
    MediumMessageStartMetadataValuesVector(b, len(val_offsets))
    for off in reversed(val_offsets):
        b.PrependUOffsetTRelative(off)
    vals_off = b.EndVector()
    MediumMessageStartMetadataKeysVector(b, len(key_offsets))
    for off in reversed(key_offsets):
        b.PrependUOffsetTRelative(off)
    keys_off = b.EndVector()
    n_str = b.CreateString("nested")
    PrimitiveTypesStart(b)
    PrimitiveTypesAddIntVal(b, 99)
    PrimitiveTypesAddFloatVal(b, 2.71)
    PrimitiveTypesAddStrVal(b, n_str)
    PrimitiveTypesAddBoolVal(b, False)
    nested_off = PrimitiveTypesEnd(b)
    MediumMessageStart(b)
    MediumMessageAddName(b, name)
    MediumMessageAddId(b, 12345)
    MediumMessageAddScores(b, scores_off)
    MediumMessageAddMetadataKeys(b, keys_off)
    MediumMessageAddMetadataValues(b, vals_off)
    MediumMessageAddNested(b, nested_off)
    off = MediumMessageEnd(b)
    b.Finish(off)
    return b.Output()


def _fb_reuse_serialize_large():
    b = _fb_builder_large
    b.Clear()
    item_offsets = []
    for i in range(100):
        name = b.CreateString(f"item_{i:04d}")
        tag_strs = [b.CreateString(f"tag_{j}") for j in range(5)]
        ComplexItemStartTagsVector(b, len(tag_strs))
        for ts in reversed(tag_strs):
            b.PrependUOffsetTRelative(ts)
        tags_off = b.EndVector()
        ComplexItemStart(b)
        ComplexItemAddName(b, name)
        ComplexItemAddId(b, i)
        ComplexItemAddScore(b, i * 1.5)
        ComplexItemAddTags(b, tags_off)
        item_offsets.append(ComplexItemEnd(b))
    LargeMessageStartItemsVector(b, len(item_offsets))
    for off in reversed(item_offsets):
        b.PrependUOffsetTRelative(off)
    items_off = b.EndVector()
    LargeMessageStart(b)
    LargeMessageAddItems(b, items_off)
    off = LargeMessageEnd(b)
    b.Finish(off)
    return b.Output()


# ── msgpack ──────────────────────────────────────────────────────────────────

def _mp_serialize_small():    return msgpack.packb(small_data)
def _mp_deserialize_small(d): _ = msgpack.unpackb(d)
def _mp_serialize_medium():   return msgpack.packb(medium_data)
def _mp_deserialize_medium(d): _ = msgpack.unpackb(d)
def _mp_serialize_large():    return msgpack.packb(large_data)
def _mp_deserialize_large(d): _ = msgpack.unpackb(d)


# ── pickle ───────────────────────────────────────────────────────────────────

def _pk_serialize_small():    return pickle.dumps(small_data)
def _pk_deserialize_small(d): _ = pickle.loads(d)
def _pk_serialize_medium():   return pickle.dumps(medium_data)
def _pk_deserialize_medium(d): _ = pickle.loads(d)
def _pk_serialize_large():    return pickle.dumps(large_data)
def _pk_deserialize_large(d): _ = pickle.loads(d)


# =============================================================================
# Benchmark runner
# =============================================================================

def bench(protocol: str, dataset: str, ser_fn, deser_fn, iterations: int = 10000):
    # warmup
    for _ in range(200):
        data = ser_fn()
        deser_fn(data)

    # size (just one run)
    data = ser_fn()
    size = len(data)

    gc.disable()

    # serialization time
    start = time.perf_counter()
    for _ in range(iterations):
        ser_fn()
    ser_us = (time.perf_counter() - start) / iterations * 1e6

    # collect garbage from ser loop before deser measurement
    gc.collect()

    # deserialization time
    start = time.perf_counter()
    for _ in range(iterations):
        deser_fn(data)
    deser_us = (time.perf_counter() - start) / iterations * 1e6

    gc.enable()

    return {
        "language": "python",
        "protocol": protocol,
        "dataset": dataset,
        "size_bytes": size,
        "serialization_time_us": round(ser_us, 3),
        "deserialization_time_us": round(deser_us, 3),
    }


# =============================================================================
# Main
# =============================================================================

PROTOCOLS = {
    "protobuf": {
        "small":  (_proto_serialize_small,  _proto_deserialize_small),
        "medium": (_proto_serialize_medium, _proto_deserialize_medium),
        "large":  (_proto_serialize_large,  _proto_deserialize_large),
    },
    "flatbuffers": {
        "small":  (_fb_serialize_small,  _fb_deserialize_small),
        "medium": (_fb_serialize_medium, _fb_deserialize_medium),
        "large":  (_fb_serialize_large,  _fb_deserialize_large),
    },
    "flatbuffers-reuse": {
        "small":  (_fb_reuse_serialize_small,  _fb_deserialize_small),
        "medium": (_fb_reuse_serialize_medium, _fb_deserialize_medium),
        "large":  (_fb_reuse_serialize_large,  _fb_deserialize_large),
    },
    "msgpack": {
        "small":  (_mp_serialize_small,  _mp_deserialize_small),
        "medium": (_mp_serialize_medium, _mp_deserialize_medium),
        "large":  (_mp_serialize_large,  _mp_deserialize_large),
    },
    "pickle": {
        "small":  (_pk_serialize_small,  _pk_deserialize_small),
        "medium": (_pk_serialize_medium, _pk_deserialize_medium),
        "large":  (_pk_serialize_large,  _pk_deserialize_large),
    },
}


def main():
    os.makedirs("results", exist_ok=True)
    results = []

    for protocol, datasets in PROTOCOLS.items():
        for dataset, (ser_fn, deser_fn) in datasets.items():
            # Use fewer iterations for large datasets to keep runtime reasonable
            iters = 2000 if dataset == "large" else 10000
            r = bench(protocol, dataset, ser_fn, deser_fn, iterations=iters)
            results.append(r)
            print(
                f"[{protocol:12s}] {dataset:6s}  "
                f"size={r['size_bytes']:6d} B  "
                f"ser={r['serialization_time_us']:8.2f} us  "
                f"des={r['deserialization_time_us']:8.2f} us"
            )

    # Write JSON for matplotlib
    out_path = "results/python_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults written to {out_path}")


if __name__ == "__main__":
    main()
