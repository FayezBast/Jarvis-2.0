# Makefile for building Go tools

BIN_DIR := ../bin

.PHONY: all clean fast-search file-indexer code-analyzer parallel-runner diff-engine symbol-resolver git-analyzer file-watcher

all: fast-search file-indexer code-analyzer parallel-runner diff-engine symbol-resolver git-analyzer file-watcher

fast-search:
	@echo "Building fast-search..."
	go build -o $(BIN_DIR)/fast-search ./cmd/fast-search

file-indexer:
	@echo "Building file-indexer..."
	go build -o $(BIN_DIR)/file-indexer ./cmd/file-indexer

code-analyzer:
	@echo "Building code-analyzer..."
	go build -o $(BIN_DIR)/code-analyzer ./cmd/code-analyzer

parallel-runner:
	@echo "Building parallel-runner..."
	go build -o $(BIN_DIR)/parallel-runner ./cmd/parallel-runner

diff-engine:
	@echo "Building diff-engine..."
	go build -o $(BIN_DIR)/diff-engine ./cmd/diff-engine

symbol-resolver:
	@echo "Building symbol-resolver..."
	go build -o $(BIN_DIR)/symbol-resolver ./cmd/symbol-resolver

git-analyzer:
	@echo "Building git-analyzer..."
	go build -o $(BIN_DIR)/git-analyzer ./cmd/git-analyzer

file-watcher:
	@echo "Building file-watcher..."
	go build -o $(BIN_DIR)/file-watcher ./cmd/file-watcher

clean:
	rm -f $(BIN_DIR)/*

# Build optimized binaries
release:
	@echo "Building optimized binaries..."
	CGO_ENABLED=0 go build -ldflags="-s -w" -o $(BIN_DIR)/fast-search ./cmd/fast-search
	CGO_ENABLED=0 go build -ldflags="-s -w" -o $(BIN_DIR)/file-indexer ./cmd/file-indexer
	CGO_ENABLED=0 go build -ldflags="-s -w" -o $(BIN_DIR)/code-analyzer ./cmd/code-analyzer
	CGO_ENABLED=0 go build -ldflags="-s -w" -o $(BIN_DIR)/parallel-runner ./cmd/parallel-runner
	CGO_ENABLED=0 go build -ldflags="-s -w" -o $(BIN_DIR)/diff-engine ./cmd/diff-engine
	CGO_ENABLED=0 go build -ldflags="-s -w" -o $(BIN_DIR)/symbol-resolver ./cmd/symbol-resolver
	CGO_ENABLED=0 go build -ldflags="-s -w" -o $(BIN_DIR)/git-analyzer ./cmd/git-analyzer
	CGO_ENABLED=0 go build -ldflags="-s -w" -o $(BIN_DIR)/file-watcher ./cmd/file-watcher
