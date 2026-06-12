.PHONY: generate-python generate-go generate all run-python run-go run plot clean

PROTOC := $(shell which protoc)
FLATC := $(shell which flatc)

PYTHON_OUT := python/generated
GO_OUT := go/generated
SCHEMA_DIR := schemas

all: generate run plot

generate: generate-python generate-go

# ── Python code generation ──
generate-python:
	mkdir -p $(PYTHON_OUT)
	$(PROTOC) -I=$(SCHEMA_DIR) \
		--python_out=$(PYTHON_OUT) \
		--pyi_out=$(PYTHON_OUT) \
		$(SCHEMA_DIR)/benchmark.proto
	$(FLATC) --python -o $(PYTHON_OUT) $(SCHEMA_DIR)/benchmark.fbs
	uv run python python/_gen_fb_init.py

# ── Go code generation ──
generate-go:
	mkdir -p $(GO_OUT)
	$(PROTOC) -I=$(SCHEMA_DIR) \
		--go_out=$(GO_OUT) \
		--go_opt=paths=source_relative \
		$(SCHEMA_DIR)/benchmark.proto
	$(FLATC) --go -o $(GO_OUT) $(SCHEMA_DIR)/benchmark.fbs

# ── Run benchmarks ──
run-python:
	mkdir -p results plots
	uv run python python/benchmark.py

run-go:
	mkdir -p results plots
	cd go && go run .

run: run-python run-go

# ── Plot ──
plot:
	uv run python python/plot.py

# ── Clean ──
clean:
	rm -rf python/generated/* go/generated/* results/*
