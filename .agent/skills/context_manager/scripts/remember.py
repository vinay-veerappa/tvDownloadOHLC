import argparse
import sys
import os

# Add current directory to sys.path to import memory_db
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from memory_db import add_memory, init_db

def main():
    parser = argparse.ArgumentParser(description="Add a new memory to the context database.")
    parser.add_argument("--category", required=True, help="Category of the memory (e.g., preference, decision)")
    parser.add_argument("--content", required=True, help="The actual content to remember")
    parser.add_argument("--tags", default="", help="Comma-separated tags for easier search")
    
    args = parser.parse_args()
    
    # Ensure DB exists
    init_db()
    
    add_memory(args.category, args.content, args.tags)

if __name__ == "__main__":
    main()
