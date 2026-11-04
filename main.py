"""Punct de intrare.  Rulare:  python main.py "Tema" "Conferinta tinta"
Poti rula si doar un pas:     python main.py --step extract|analyze|write "Tema" "Conf"
"""
import argparse

from agents import analyst, extractor, writer

p = argparse.ArgumentParser()
p.add_argument("topic", nargs="?", default="Tema lucrarii")
p.add_argument("venue", nargs="?", default="Conferinta tinta")
p.add_argument("--step", choices=["extract", "analyze", "write", "all"], default="all")
a = p.parse_args()

if a.step in ("extract", "all"):
    extractor.run()
if a.step in ("analyze", "all"):
    analyst.run(a.topic)
if a.step in ("write", "all"):
    writer.run(a.topic, a.venue)
print("Gata. Vezi folderul out/")