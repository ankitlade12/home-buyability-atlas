"""Export the manuscript for editorial review, with IEEE numeric citations.

Requires pypandoc_binary (installed in the project environment).
This is an editable review copy, not the conference's Word template.
"""
import os
import re
import json
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree
import pypandoc

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT/'paper')
source = Path('draft.tex').read_text().replace(
    '../outputs/representation_comparison.pdf', '../outputs/representation_comparison.png').replace(
    '../outputs/payment_burden_pilot.pdf', '../outputs/payment_burden_pilot.png')
# Pandoc does not interpret IEEEauthorblock macros; use standard author metadata
# for the review copy while retaining the IEEE blocks in the PDF source.
authors = json.loads(Path('edas_submission.json').read_text()).get('authors', [])
if authors:
    author_text = r' \and '.join(
        r' \\ '.join([a['name'], a['affiliation'], a['email']]) for a in authors)
    start, end = source.index(r'\author{'), source.index(r'\begin{document}')
    source = source[:start] + '\\author{' + author_text + '}\n' + source[end:]
# Supply URLs as structured bibliography fields rather than capitalized prose.
bib = re.sub(r'howpublished=\{\\url\{([^}]+)\}\}', r'url={\1}', Path('references.bib').read_text())
reference_file = ROOT/'outputs/word_references.bib'
reference_file.write_text(bib)
output = ROOT/'outputs/home_buyability_review.docx'
pypandoc.convert_text(source, 'docx', format='latex', outputfile=str(output),
    extra_args=['--standalone', '--citeproc', f'--bibliography={reference_file}',
                '--csl=ieee.csl', '--metadata=reference-section-title:References',
                '--resource-path=.:../outputs'])
with ZipFile(output) as archive:
    xml = archive.read('word/document.xml')
    text = ''.join(ElementTree.fromstring(xml).itertext())
    assert all(value in text for value in ['1,682', '65.8', 'References', 'Conclusion'])
    assert any(name.startswith('word/media/') for name in archive.namelist())
    assert b'<m:oMath>' in xml
    assert all(value in text for author in authors for value in author.values())
print(output)
