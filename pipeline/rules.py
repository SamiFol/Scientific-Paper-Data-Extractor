"""The global rules shared by analyst, writer and reviewer. The text lives in prompts/global_rules.md."""
from pipeline import prompts

GLOBAL_RULES = prompts.load("global_rules")
