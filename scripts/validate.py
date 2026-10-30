#!/usr/bin/env python3
"""Проверка онтологии ISEC и демонстрационных данных.

Запуск из корня репозитория:
    pip install -r requirements.txt
    python scripts/validate.py

Проверяется: синтаксис Turtle, состав модели, наличие русских и английских
меток, области определения и значений свойств, непротиворечивость
(замыкание OWL-RL), выполнение запросов из каталога queries/ на примере данных.
"""
import sys
from pathlib import Path

import owlrl
import rdflib
from rdflib.namespace import OWL, RDF, RDFS

ROOT = Path(__file__).resolve().parent.parent
ONTO = ROOT / "ontology" / "isec_ontology.ttl"
DATA = ROOT / "examples" / "example_system.ttl"
QUERIES = sorted((ROOT / "queries").glob("*.rq"))

errors = []


def check(cond, msg):
    print(("  OK   " if cond else "  FAIL ") + msg)
    if not cond:
        errors.append(msg)


def short(term):
    s = str(term)
    return s.split("#")[-1] if "#" in s else s


print("1. Синтаксис и состав")
g = rdflib.Graph()
g.parse(ONTO, format="turtle")
NS = dict(g.namespaces())["isec"]
count = lambda t: len({s for s in g.subjects(RDF.type, t) if str(s).startswith(str(NS))})
classes = {s for s in g.subjects(RDF.type, OWL.Class) if str(s).startswith(str(NS))}
objprops = {s for s in g.subjects(RDF.type, OWL.ObjectProperty) if str(s).startswith(str(NS))}
dtprops = {s for s in g.subjects(RDF.type, OWL.DatatypeProperty) if str(s).startswith(str(NS))}
individuals = {s for s, o in g.subject_objects(RDF.type) if str(s).startswith(str(NS)) and o in classes}
print(f"  триплетов: {len(g)}; классов: {len(classes)}; объектных свойств: {len(objprops)}; "
      f"свойств типов данных: {len(dtprops)}; аннотационных: {count(OWL.AnnotationProperty)}; индивидов: {len(individuals)}")
check((len(classes), len(objprops), len(dtprops), len(individuals)) == (17, 29, 8, 13),
      "состав соответствует описанию: 17 / 29 / 8 / 13")

print("2. Метки")
for term in sorted(classes | objprops | dtprops):
    langs = {l.language for l in g.objects(term, RDFS.label)}
    check({"ru", "en"} <= langs, f"метки ru и en: {short(term)}") if not {"ru", "en"} <= langs else None
check(all({"ru", "en"} <= {l.language for l in g.objects(t, RDFS.label)} for t in classes | objprops | dtprops),
      "у всех классов и свойств есть метки на русском и английском")

print("3. Области определения и значений")
no_domain = [short(p) for p in objprops if g.value(p, RDFS.domain) is None]
no_range = [short(p) for p in objprops if g.value(p, RDFS.range) is None]
check(no_range == [], "область значений задана у всех объектных свойств")
check(no_domain in ([], ["referencesKnowledgeBase"]),
      f"область определения не задана только у referencesKnowledgeBase (документированное исключение): {no_domain}")

print("4. Аннотации происхождения")
src = rdflib.URIRef(str(NS) + "sourcedFrom")
dec = rdflib.URIRef(str(NS) + "designDecision")
print(f"  конструкций с isec:sourcedFrom: {len(set(g.subjects(src, None)))}; "
      f"с isec:designDecision: {len(set(g.subjects(dec, None)))}")

print("5. Непротиворечивость (замыкание OWL-RL)")
for name, graph_files in [("онтология", [ONTO]), ("онтология + пример данных", [ONTO, DATA])]:
    h = rdflib.Graph()
    for f in graph_files:
        h.parse(f, format="turtle")
    before = len(h)
    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(h)
    nothing = list(h.subjects(RDF.type, OWL.Nothing))
    print(f"  {name}: {before} -> {len(h)} триплетов")
    check(not nothing, f"{name}: экземпляры owl:Nothing не выведены")

print("6. Запросы на примере данных (без логического вывода)")
d = rdflib.Graph()
d.parse(ONTO, format="turtle")
d.parse(DATA, format="turtle")
for q in QUERIES:
    rows = list(d.query(q.read_text(encoding="utf-8")))
    print(f"  {q.name}: строк {len(rows)}")
    for r in rows:
        print("     " + " | ".join(short(v) if v is not None else "-" for v in r))
    check(len(rows) > 0, f"{q.name} возвращает непустой результат")

print()
if errors:
    print(f"Ошибок: {len(errors)}")
    sys.exit(1)
print("Все проверки пройдены.")
