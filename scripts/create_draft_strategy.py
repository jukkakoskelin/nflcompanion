"""Persist an interactive or simulated draft strategy into durable draft context."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from nflcompanion.state_store import save_draft_strategy, simulate_draft_strategy


def _json_argument(value: str, *, argument_name: str) -> object:
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{argument_name} must be valid JSON: {exc}") from exc


def _validate_questionnaire(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise SystemExit("--questionnaire-json must decode to a list")
    questionnaire: list[dict[str, str]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise SystemExit(f"--questionnaire-json item {index} must be an object")
        question = item.get("question")
        answer = item.get("answer")
        if not isinstance(question, str) or not question.strip():
            raise SystemExit(f"--questionnaire-json item {index} must include a non-empty string question")
        if not isinstance(answer, str) or not answer.strip():
            raise SystemExit(f"--questionnaire-json item {index} must include a non-empty string answer")
        questionnaire.append({"question": question, "answer": answer})
    return questionnaire


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, default=Path("state"))
    parser.add_argument("--league-id", required=True)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--draft-style", choices=("sleeper_dynasty", "espn_snake"), required=True)
    parser.add_argument("--name")
    parser.add_argument("--reverse-round", action="store_true")
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--strategy-json")
    parser.add_argument("--questionnaire-json")
    parser.add_argument("--validation-feedback-json")
    args = parser.parse_args()

    if args.simulate:
        strategy = simulate_draft_strategy(
            args.state_root,
            league_id=args.league_id,
            season=args.season,
            draft_style=args.draft_style,
            reverse_round=args.reverse_round,
            seed=args.seed,
        )
    else:
        if not args.name:
            parser.error("--name is required unless --simulate is used")
        if not args.strategy_json:
            parser.error("--strategy-json is required unless --simulate is used")
        strategy_payload = _json_argument(args.strategy_json, argument_name="--strategy-json")
        questionnaire = []
        if args.questionnaire_json:
            questionnaire = _validate_questionnaire(
                _json_argument(args.questionnaire_json, argument_name="--questionnaire-json")
            )
        validation_feedback = None
        if args.validation_feedback_json:
            validation_feedback = _json_argument(
                args.validation_feedback_json,
                argument_name="--validation-feedback-json",
            )
        if not isinstance(strategy_payload, dict):
            parser.error("--strategy-json must decode to an object")
        if validation_feedback is not None and not isinstance(validation_feedback, list):
            parser.error("--validation-feedback-json must decode to a list")
        strategy = save_draft_strategy(
            args.state_root,
            league_id=args.league_id,
            season=args.season,
            draft_style=args.draft_style,
            reverse_round=args.reverse_round,
            name=args.name,
            strategy=strategy_payload,
            questionnaire=questionnaire,
            validation_feedback=validation_feedback,
        )

    print(json.dumps(strategy, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
