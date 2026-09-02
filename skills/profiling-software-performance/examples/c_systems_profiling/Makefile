CC ?= clang
CFLAGS ?= -O2 -Wall -Wextra -g -fno-omit-frame-pointer

TARGET = matrix_traversal_benchmark
SRC = matrix_traversal_benchmark.c

.PHONY: all clean run

all: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) -o $(TARGET) $(SRC)

run: $(TARGET)
	./$(TARGET)

clean:
	rm -rf $(TARGET) *.dSYM
