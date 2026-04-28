#!/usr/bin/env python3
"""CLI for YouTube clickbait detector."""

import argparse
import sys
import time
from dotenv import load_dotenv

from src.youtube_fetcher import fetch_video_data
from src.clickbait_analyzer import analyze_for_clickbait


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Analyze YouTube videos for clickbait"
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="YouTube video URL to analyze"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show full description and transcript"
    )
    parser.add_argument(
        "--webserver",
        action="store_true",
        help="Launch web UI on port 4004"
    )

    args = parser.parse_args()

    # Launch web server mode
    if args.webserver:
        from src.webserver import run_server
        print("Starting YouTube Clickbait Detector web UI...")
        print("Open http://localhost:4004 in your browser")
        run_server()
        return

    # CLI mode requires URL
    if not args.url:
        parser.print_help()
        sys.exit(1)

    # Fetch metadata
    video_data = fetch_video_data(args.url, verbose=False)

    # Print title
    print(f"Title: {video_data['title']}")

    # Print description if verbose
    if args.verbose:
        print(f"Description: {video_data['description']}")

    print("-" * 35)

    # Initial analysis (metadata only)
    initial_analysis = analyze_for_clickbait(
        title=video_data['title'],
        description=video_data['description'],
        transcript=None
    )
    print(f"Initial score: {initial_analysis.clickbait_score}% clickbait")

    # Download and transcribe audio if no transcript available
    if not video_data['transcript']:
        print("Downloading audio..")
        audio_start = time.time()

        print("Transcribing audio....")
        video_data = fetch_video_data(args.url, verbose=False)
        total_time = time.time() - audio_start

        if video_data['transcript']:
            analysis = analyze_for_clickbait(
                title=video_data['title'],
                description=video_data['description'],
                transcript=video_data['transcript']
            )
            print(f"Done in {total_time:.1f} seconds")
            print(f"Transcription score: {analysis.clickbait_score}% clickbait")

            print("\n" + "-" * 35)
            verdict = 'CLICKBAIT' if analysis.is_clickbait else 'NOT CLICKBAIT'
            print(f"Analysis: {verdict} ({analysis.clickbait_score}/100 pts)")
            print()
            print(analysis.reasoning)

            if args.verbose:
                print("\n" + "-" * 35)
                print("Full transcript:")
                print(video_data['transcript'])
        else:
            print("Could not transcribe audio.")
            print("\n" + "-" * 35)
            print(initial_analysis.reasoning)
    else:
        # Transcript available from cache or API
        analysis = analyze_for_clickbait(
            title=video_data['title'],
            description=video_data['description'],
            transcript=video_data['transcript']
        )
        print("\n" + "-" * 35)
        print(f"Analysis: {'CLICKBAIT' if analysis.is_clickbait else 'NOT CLICKBAIT'} ({analysis.clickbait_score}%)")
        print()
        print(analysis.reasoning)

        if args.verbose:
            print("\n" + "-" * 35)
            print("Full transcript:")
            print(video_data['transcript'])


if __name__ == "__main__":
    main()
