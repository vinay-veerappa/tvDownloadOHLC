import sys

def peek_file(path, lines=5):
    try:
        with open(path, 'r') as f:
            print(f"--- First {lines} lines of {path} ---")
            for _ in range(lines):
                line = f.readline()
                if not line: break
                print(line.strip())
    except Exception as e:
        print(f"Error reading file: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        peek_file(sys.argv[1])
    else:
        print("Usage: peek_file.py <path>")
