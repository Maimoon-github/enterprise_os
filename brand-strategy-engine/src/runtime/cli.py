"""Terminal command line entrypoint for Universal AI Brand Strategy Engine."""

import argparse
import asyncio
import json
import sys
from typing import Optional

from src.orchestrator.manager import StrategyOrchestrator
from src.schemas.state import BrandProfile, OperationalMode


async def run_cli(
    mode_str: str,
    url: str,
    docs_dir: Optional[str] = None,
    brand_name: Optional[str] = None,
    industry: Optional[str] = None,
) -> int:
    """Executes the strategy audit from the CLI."""
    print(f"🚀 Initializing Universal AI Brand Strategy Engine [{mode_str}]...")
    print(f"🎯 Target URL: {url}")

    try:
        mode = OperationalMode(mode_str)
    except ValueError:
        print(f"❌ Invalid mode: {mode_str}. Must be 'Mode_A_Personal' or 'Mode_B_eCommerce'.")
        return 1

    b_name = brand_name or ("Personal Portfolio" if mode == OperationalMode.MODE_A_PERSONAL else "eCommerce Merchant")
    ind = industry or ("Software & Technology" if mode == OperationalMode.MODE_A_PERSONAL else "Consumer Goods / DTC")

    profile = BrandProfile(
        website_url=url,
        brand_name=b_name,
        industry=ind,
        target_market=["Enterprise Decision Makers", "High-Value Clients"]
        if mode == OperationalMode.MODE_A_PERSONAL
        else ["High-Intent Online Shoppers"],
        business_goals=["Increase inbound inquiry conversion rate to >4%"]
        if mode == OperationalMode.MODE_A_PERSONAL
        else ["Reduce mobile PDP bounce rate and lift Add-to-Cart CVR"],
    )

    orchestrator = StrategyOrchestrator()
    print("⏳ Executing autonomous multi-agent reconnaissance and adversarial verification...")
    state = await orchestrator.execute_audit(
        brand_profile=profile,
        mode=mode,
        docs_dir=docs_dir,
    )

    dossier = orchestrator.compile_final_strategy_dossier(state)

    print("\n" + "=" * 60)
    print("📊 BRAND STRATEGY DOSSIER COMPILED")
    print(f"Session ID:         {dossier['session_id']}")
    print(f"Validation Status:  {dossier['validation_status']}")
    print(f"Total Approved:     {dossier['total_initiatives']}")
    print("=" * 60)

    for idx, init in enumerate(dossier["approved_initiatives"], 1):
        print(f"\n[Initiative #{idx}] {init['recommendation_id']}")
        print(f"  Finding:     {init['finding']}")
        print(f"  Action:      {init['actionable_prescription']}")
        print(f"  KPI Target:  {init['success_metric']['kpi']} -> {init['success_metric']['target']}")
        print(f"  ICE Score:   {init['priority']['ice_score']} / 10.0")

    print("\n✅ Strategy run concluded successfully.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Universal AI Brand Strategy Engine CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="Mode_A_Personal",
        choices=["Mode_A_Personal", "Mode_B_eCommerce"],
        help="Operating mode",
    )
    parser.add_argument(
        "--url",
        type=str,
        required=True,
        help="Target website URL to inspect and audit",
    )
    parser.add_argument(
        "--docs-dir",
        type=str,
        default=None,
        help="Path to directory containing client pitch decks, PDFs, or guidelines",
    )
    parser.add_argument(
        "--brand-name",
        type=str,
        default=None,
        help="Brand or personal professional name",
    )
    parser.add_argument(
        "--industry",
        type=str,
        default=None,
        help="Industry vertical or specialized niche",
    )

    args = parser.parse_args()
    exit_code = asyncio.run(
        run_cli(
            mode_str=args.mode,
            url=args.url,
            docs_dir=args.docs_dir,
            brand_name=args.brand_name,
            industry=args.industry,
        )
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
