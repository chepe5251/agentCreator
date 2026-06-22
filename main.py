import asyncio
import argparse
import sys
import uuid
from datetime import datetime
from agent_factory.orchestrator import EnterpriseOrchestrator
from agent_factory.config import validate_default_models

async def main():
    parser = argparse.ArgumentParser(description="Agent Factory Enterprise - Orchestrator CLI")
    parser.add_argument(
        "--prompt", 
        type=str, 
        required=True, 
        help="The target project idea or requirements description to build."
    )
    parser.add_argument(
        "--run-id", 
        type=str, 
        default=None, 
        help="Optional unique identifier for this project run."
    )
    args = parser.parse_args()
    
    ok, error = validate_default_models()
    if not ok:
        print("[!] Error: LLM configuration is incomplete.", file=sys.stderr)
        print(f"[!] {error}", file=sys.stderr)
        sys.exit(1)
        
    run_id = args.run_id
    if not run_id:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_id = str(uuid.uuid4())[:8]
        run_id = f"run_{timestamp}_{short_id}"
        
    orchestrator = EnterpriseOrchestrator(run_id, args.prompt)
    
    try:
        approved, summary = await orchestrator.run()
        print("\n=================== FINAL SUMMARY ===================")
        print(summary)
        print("=====================================================")
        
        if approved:
            print("[+] Build Completed: The project deliverables were APPROVED by the auditors.")
            sys.exit(0)
        else:
            print("[!] Build Failed: The project deliverables were REJECTED after max iterations.")
            sys.exit(2)
            
    except KeyboardInterrupt:
        print("\n[!] Execution interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\n[!] Critical error during orchestrator execution: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
