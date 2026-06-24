"""
Main entry point - 多轮轨迹生成脚本

Usage:
    python generate.py [--num 3] [--output ./output] [--domain code_development]
"""
import argparse
import json
import random
from pathlib import Path

from src.domain import load_domain
from src.task_generator import generate_blueprint
from src.planner import plan_multi_turn
from src.generator import generate_multi_turn_trajectory


def main():
    parser = argparse.ArgumentParser(description="Multi-turn Agent Trajectory Generator")
    parser.add_argument("--num",      type=int, default=3,                 help="Number of trajectories")
    parser.add_argument("--output",   type=str, default="./output",        help="Output directory")
    parser.add_argument("--domain",   type=str, default="code_development", help="Domain name")
    parser.add_argument("--personas", type=str, default="../personas",      help="Personas directory")
    args = parser.parse_args()

    base_dir     = Path(__file__).parent
    domain_dir   = base_dir / "domain" / args.domain
    personas_dir = (base_dir / args.personas).resolve()
    output_dir   = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n\033[1m══ Multi-turn Trajectory Generator ══\033[0m")
    print(f"\033[36m→ Domain:   {args.domain}\033[0m")
    print(f"\033[36m→ Personas: {personas_dir}\033[0m")
    print(f"\033[36m→ Target:   {args.num} trajectories\033[0m\n")

    domain = load_domain(domain_dir, personas_dir)
    print(f"  Loaded {len(domain.skills)} skills, {len(domain.tools)} tools, "
          f"{len(domain.user_profiles)} personas, {len(domain.trajectory_templates)} templates\n")

    if not domain.user_profiles:
        print("\033[31m✗ No user profiles found!\033[0m")
        return

    trajectories = []

    for i in range(args.num):
        user_data  = random.choice(domain.user_profiles)
        persona_id = user_data.get("_meta", {}).get("personaId", f"user_{i}")
        print(f"\033[36m── [{i+1}/{args.num}] {persona_id} ──\033[0m")

        try:
            # Step 1: Generate blueprint (with conversation arc)
            print("  1. Generating blueprint...")
            blueprint = generate_blueprint(domain, user_data)
            print(f"     Task type:  {blueprint.task_type}")
            print(f"     Arc turns:  {len(blueprint.conversation_arc)}"
                  f" {[t.trigger for t in blueprint.conversation_arc]}")
            print(f"     Query:      {blueprint.initial_user_query[:70]}...")

            # Step 2: Plan multi-turn trajectory
            print("  2. Planning multi-turn trajectory (LLM)...")
            multi_plan = plan_multi_turn(domain, blueprint, user_data["profile"], use_llm=True)
            for tp in multi_plan["turns_plan"]:
                node_names = [n.get("skill_id") or n.get("tool_id") or n.get("node_name", "")
                              for n in tp["planned_nodes"]]
                print(f"     Turn {tp['turn_id']} ({tp['trigger']}): {' → '.join(filter(None, node_names))}")

            # Step 3: Generate full multi-turn trajectory
            print("  3. Generating turn content (LLM)...")
            trajectory = generate_multi_turn_trajectory(multi_plan, domain, use_llm=True)
            print(f"     Generated {len(trajectory.turns)} turns")
            for turn in trajectory.turns:
                print(f"     Turn {turn.turn_id}: {len(turn.processing_nodes)} nodes | "
                      f"response: {len(turn.agent_response)} chars")

            trajectories.append(trajectory)
            print(f"  \033[32m✓ Done\033[0m\n")

        except Exception as e:
            print(f"  \033[31m✗ Failed: {e}\033[0m\n")
            import traceback
            traceback.print_exc()

    # Export
    if trajectories:
        jsonl_path = output_dir / "trajectories.jsonl"
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for t in trajectories:
                f.write(json.dumps(t.to_dict(), ensure_ascii=False) + "\n")

        individual_dir = output_dir / "individual"
        individual_dir.mkdir(exist_ok=True)
        for t in trajectories:
            fpath = individual_dir / f"{t.trajectory_id}.json"
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(t.to_dict(), f, ensure_ascii=False, indent=2)

        print(f"\033[32m══ Results ══\033[0m")
        print(f"  Generated: {len(trajectories)}/{args.num} trajectories")
        print(f"  JSONL:     {jsonl_path}")
        print(f"  Individual:{individual_dir}/")
    else:
        print("\n\033[31m✗ No trajectories generated\033[0m")


if __name__ == "__main__":
    main()
