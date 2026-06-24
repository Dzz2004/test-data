"""
Main entry point - 轨迹生成脚本

Usage:
    python generate.py [--num 5] [--output ./output]
"""
import argparse
import json
import time
from pathlib import Path

from src.domain import load_domain
from src.task_generator import generate_task
from src.planner import plan_with_llm
from src.generator import generate_trajectory


def main():
    parser = argparse.ArgumentParser(description="Agent Trajectory Generator")
    parser.add_argument("--num", type=int, default=3, help="Number of trajectories to generate")
    parser.add_argument("--output", type=str, default="./output", help="Output directory")
    parser.add_argument("--domain", type=str, default="code_development", help="Domain name")
    parser.add_argument("--personas", type=str, default="../personas", help="Personas directory")
    args = parser.parse_args()

    base_dir = Path(__file__).parent
    domain_dir = base_dir / "domain" / args.domain
    personas_dir = (base_dir / args.personas).resolve()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load domain
    print(f"\n\033[1m══ Trajectory Generator ══\033[0m")
    print(f"\033[36m→ Domain: {args.domain}\033[0m")
    print(f"\033[36m→ Personas: {personas_dir}\033[0m")
    print(f"\033[36m→ Target: {args.num} trajectories\033[0m\n")

    domain = load_domain(domain_dir, personas_dir)
    print(f"  Loaded {len(domain.skills)} skills, {len(domain.tools)} tools, {len(domain.user_profiles)} personas")

    if not domain.user_profiles:
        print("\033[31m✗ No user profiles found!\033[0m")
        return

    # Generate trajectories
    trajectories = []
    import random

    for i in range(args.num):
        user_data = random.choice(domain.user_profiles)
        persona_id = user_data.get("_meta", {}).get("personaId", f"user_{i}")
        print(f"\n\033[36m── [{i+1}/{args.num}] Generating for: {persona_id} ──\033[0m")

        try:
            # Step 1: Generate task
            print("  1. Generating task...")
            task = generate_task(domain, user_data)
            print(f"     Task type: {task['task_type']}")
            print(f"     Query: {task['initial_user_query'][:60]}...")

            # Step 2: Plan trajectory (LLM-driven with template fallback)
            print("  2. Planning trajectory (LLM)...")
            plan = plan_with_llm(domain, task, user_data["profile"])
            print(f"     Method: {plan.get('planning_method', 'unknown')}")
            print(f"     Planned {len(plan['planned_nodes'])} nodes")

            # Step 3: Generate full trajectory
            print("  3. Generating trajectory content...")
            trajectory = generate_trajectory(plan, domain)
            print(f"     Generated {len(trajectory['nodes'])} nodes, {len(trajectory['edges'])} edges")

            trajectories.append(trajectory)
            print(f"  \033[32m✓ Done\033[0m")

        except Exception as e:
            print(f"  \033[31m✗ Failed: {e}\033[0m")
            import traceback
            traceback.print_exc()

    # Export
    if trajectories:
        # JSONL output
        jsonl_path = output_dir / "trajectories.jsonl"
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for t in trajectories:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")

        # Also write individual files for inspection
        individual_dir = output_dir / "individual"
        individual_dir.mkdir(exist_ok=True)
        for t in trajectories:
            fpath = individual_dir / f"{t['trajectory_id']}.json"
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(t, f, ensure_ascii=False, indent=2)

        print(f"\n\033[32m══ Results ══\033[0m")
        print(f"  Generated: {len(trajectories)}/{args.num} trajectories")
        print(f"  JSONL: {jsonl_path}")
        print(f"  Individual: {individual_dir}/")
    else:
        print("\n\033[31m✗ No trajectories generated\033[0m")


if __name__ == "__main__":
    main()
