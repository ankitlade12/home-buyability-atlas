"""Build the IEEE conference PDF and check basic submission properties."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--paper-size', choices=['a4', 'letter'], default='a4')
    args = parser.parse_args()
    build = ROOT/'outputs/latex'
    build.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env['TEXINPUTS'] = str(ROOT/'paper/template') + os.pathsep + env.get('TEXINPUTS', '')
    env['BSTINPUTS'] = str(ROOT/'paper/template') + os.pathsep + env.get('BSTINPUTS', '')
    env['BIBINPUTS'] = str(ROOT/'paper') + os.pathsep + env.get('BIBINPUTS', '')
    env['TEXMFVAR'] = str(build/'tex-cache')
    source = r'\def\UseLetterPaper{1}\input{draft.tex}' if args.paper_size == 'letter' else 'draft.tex'
    latex = ['pdflatex', '-interaction=nonstopmode', '-halt-on-error',
             '-jobname=manuscript', f'-output-directory={build}', source]
    with (build/'build.log').open('w') as log:
        for command, cwd in [(latex, ROOT/'paper'), (['bibtex', 'manuscript'], build),
                             (latex, ROOT/'paper'), (latex, ROOT/'paper')]:
            subprocess.run(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    logfile = (build/'manuscript.log').read_text()
    assert 'undefined references' not in logfile and 'undefined citations' not in logfile
    assert 'Overfull' not in logfile, 'Layout overflow: inspect outputs/latex/manuscript.log'
    pdf = build/'manuscript.pdf'
    reader = PdfReader(pdf)
    assert not reader.is_encrypted and not reader.outline
    fonts = {}
    for page in reader.pages:
        assert not page.get('/Annots'), 'Unexpected PDF annotations or links'
        for value in page['/Resources'].get('/Font', {}).values():
            font = value.get_object()
            descendant = font.get('/DescendantFonts')
            descriptor = (descendant[0].get_object() if descendant else font).get('/FontDescriptor')
            embedded = descriptor is not None and any(k in descriptor.get_object() for k in ['/FontFile', '/FontFile2', '/FontFile3'])
            assert embedded, f'Font not embedded: {font.get("/BaseFont")}'
            fonts[str(font.get('/BaseFont'))] = embedded
    target = ROOT/f'outputs/comnetsat2026_buyability_{args.paper_size}.pdf'
    shutil.copyfile(pdf, target)
    result = {'pdf':str(target.relative_to(ROOT)), 'pages':len(reader.pages), 'paper_size':args.paper_size,
              'page_dimensions_points':list(map(float,reader.pages[0].mediabox[2:])),
              'all_fonts_embedded':True,'fonts':list(fonts),'annotations':False,'bookmarks':False,
              'no_page_numbers_headers_footers':'Enforced by empty page style; visually inspect PDF',
              'status':'Formatted draft; scientific review and final venue checks remain incomplete. Not PDF eXpress certified.'}
    (ROOT/f'outputs/paper_build_{args.paper_size}.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__ == '__main__':
    main()
