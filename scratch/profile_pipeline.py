import cProfile
import pstats
import sys
import os

# Add REPO_ROOT to sys.path so we can import scripts
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.streaming.options.run_options_levels import run_pipeline

def profile_run():
    # Run the pipeline for SPX (which resolves to /ES for RTD) without Discord notifications
    run_pipeline(
        tickers=["SPX"],
        run_label="profile_test",
        enable_discord=False,
        full_discord=False,
        versioned=False,
    )

def main():
    print("Starting profiling run for SPX...")
    profiler = cProfile.Profile()
    profiler.enable()
    
    try:
        profile_run()
    finally:
        profiler.disable()
        print("\nProfiling completed. Statistics:")
        stats = pstats.Stats(profiler, stream=sys.stdout)
        stats.sort_stats(pstats.SortKey.CUMULATIVE)
        stats.print_stats(50)  # Print top 50 functions
        
        # Save results to a file
        stats.dump_stats("C:\\Users\\vinay\\.gemini\\antigravity\\brain\\ffbdbe3d-2f7c-47ed-a3ce-10ba9f0aae83\\pipeline_profile.stats")
        print("\nSaved profile dump to C:\\Users\\vinay\\.gemini\\antigravity\\brain\\ffbdbe3d-2f7c-47ed-a3ce-10ba9f0aae83\\pipeline_profile.stats")

if __name__ == "__main__":
    main()
