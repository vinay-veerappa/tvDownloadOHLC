import argparse
import sys
import os

# Add current directory to sys.path to import memory_db
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from memory_db import search_memories, init_db

def main():
    parser = argparse.ArgumentParser(description="Search for memories in the context database.")
    parser.add_argument("--query", help="Text to search for in content and tags")
    parser.add_argument("--category", help="Filter by category")
    parser.add_argument("--limit", type=int, default=10, help="Max number of results to return")
    
    args = parser.parse_args()
    
    # Ensure DB exists
    init_db()
    
    results = search_memories(query=args.query, category=args.category, limit=args.limit)
    
    if not results:
        print("No memories found.")
    else:
        for mem in results:
            print(f"[{mem['id']}] {mem['created_at']} | [{mem['category']}] {mem['content']} (Tags: {mem['tags']})")

if __name__ == "__main__":
    main()
