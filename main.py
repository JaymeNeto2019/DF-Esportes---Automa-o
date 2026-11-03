"""DF Esportes: RSS -> arte PNG + legenda -> Telegram.
Python 3.11+, Pillow. Sem IA paga e sem serviços intermediários.
"""
import io
import json
import os
import re
import sys
import textwrap
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

FEED = 'https://dfesportes.com/feed/'
STATE = Path('seen.json')
OUTPUT = Path('preview')
UA = 'DFEsportesBot/1.0 (+https://dfesportes.com)'
CONTENT_NS = '{http://purl.org/rss/1.0/modules/content/}'


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


class ArticleHTML(HTMLParser):
    """Pega primeiro parágrafo editorial e foto principal, ignorando p vazios."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.p_depth = 0
        self.capture = False
        self.buf = []
        self.paragraphs = []
        self.image = None
        self.credit = None
        self.in_caption = False
        self.caption_buf = []
        self.figure_count = 0
        self.first_figure_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get('class', '').split()
        if tag == 'figure':
            self.figure_count += 1
            if self.figure_count == 1:
                self.first_figure_depth = 1
        elif self.first_figure_depth and tag == 'figure':
            self.first_figure_depth += 1
        if tag == 'img' and self.first_figure_depth and self.image is None:
            self.image = attrs.get('src')
        if tag == 'figcaption' and self.first_figure_depth == 1:
            self.in_caption = True
        if tag == 'p':
            self.p_depth += 1
            if self.p_depth == 1:
                self.capture = 'wp-block-paragraph' in classes
                self.buf = []

    def handle_data(self, data):
        if self.capture:
            self.buf.append(data)
        if self.in_caption:
            self.caption_buf.append(data)

    def handle_endtag(self, tag):
        if tag == 'p' and self.p_depth:
            if self.p_depth == 1 and self.capture:
                s = ' '.join(''.join(self.buf).split())
                if s:
                    self.paragraphs.append(s)
            self.p_depth -= 1
            if not self.p_depth:
                self.capture = False
        if tag == 'figcaption' and self.in_caption:
            self.credit = ' '.join(''.join(self.caption_buf).split())
            self.in_caption = False
        if tag == 'figure' and self.first_figure_depth:
            self.first_figure_depth -= 1


def read_feed(xml):
    root = ET.fromstring(xml)
    items = []
    for node in root.findall('./channel/item'):
        def value(name):
            return (node.findtext(name) or '').strip()
        html = node.findtext(CONTENT_NS + 'encoded') or ''
        parser = ArticleHTML()
        parser.feed(html)
        # Há artigos com legenda editorial antes do lead; evita textos tipicamente de crédito.
        candidate = next((p for p in parser.paragraphs if len(p) >= 95 and not p.lower().startswith(('foto:', 'fotos:', 'crédito:', 'imagem:'))), '')
        if not candidate:
            candidate = next((p for p in parser.paragraphs if len(p) >= 45), '')
        categories = [el.text or '' for el in node.findall('category')]
        preferred = next((c for c in categories if c.casefold() in ('basquete', 'futebol candango', 'futebol nacional', 'artes marciais', 'mais esportes')), None)
        cat = preferred or next((c for c in categories if c.casefold() != 'destaques'), 'ESPORTES')
        raw_link = value('link')
        parsed = urllib.parse.urlsplit(raw_link)
        link = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', ''))
        items.append({'id': value('guid') or link, 'title': value('title'), 'lead': candidate,
                      'image': parser.image, 'credit': parser.credit or '', 'category': cat, 'link': link})
    return items


def font(size, bold=False):
    candidates = ([
        'assets/NotoSans-Bold.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf'] if bold else [
        'assets/NotoSans-Regular.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'])
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def wrap(draw, text, f, max_width):
    words = text.split()
    lines = []
    current = ''
    for word in words:
        new = (current + ' ' + word).strip()
        if draw.textlength(new, font=f) <= max_width:
            current = new
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def art(item, filename):
    W, H = 1080, 1350
    canvas = Image.new('RGB', (W, H), '#101018')
    d = ImageDraw.Draw(canvas)
    # Foto em destaque, sem esticar; padronização vertical.
    if item['image']:
        try:
            img = Image.open(io.BytesIO(fetch(item['image']))).convert('RGB')
            img = ImageOps.fit(img, (W, 1180), method=Image.Resampling.LANCZOS, centering=(.5, .36))
            canvas.paste(img, (0, 100))
        except Exception as exc:
            print('Aviso: foto indisponível:', exc)
    # Gradiente escuro para legibilidade; roxo da identidade do portal.
    overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    px = overlay.load()
    for y in range(470, H):
        p = (y - 470) / (H - 470)
        alpha = int(min(244, 10 + 235 * p ** 1.5))
        for x in range(W):
            px[x, y] = (38, 4, 65, alpha)
    canvas = Image.alpha_composite(canvas.convert('RGBA'), overlay)
    d = ImageDraw.Draw(canvas)
    d.rectangle((0, 0, W, 104), fill='#101019')
    d.rectangle((0, 100, W, 108), fill='#F59D00')
    # Identidade visual textual temporária, substituível pelo logo oficial.
    if Path('assets/logo.png').exists():
        logo = Image.open('assets/logo.png').convert('RGBA')
        logo.thumbnail((430, 83))
        canvas.alpha_composite(logo, (W - logo.width - 38, 10))
    else:
        d.text((W - 335, 23), 'DF ESPORTES', font=font(44, True), fill='#FFFFFF')
        d.text((W - 76, 70), '.COM', font=font(21, True), fill='#F59D00')
    d.rectangle((45, 820, 60, 849), fill='#F59D00')
    label = item['category'].upper()[:24]
    label_font = font(25, True)
    label_w = int(d.textlength(label, font=label_font)) + 40
    d.rounded_rectangle((70, 803, 70 + label_w, 858), radius=23, fill='#66128D')
    d.text((90, 814), label, font=label_font, fill='white')
    # Encaixe dinâmico do título em no máximo 6 linhas.
    title = ' '.join(item['title'].upper().split())
    available_width = W - 106
    for size in range(61, 30, -2):
        f = font(size, True)
        lines = wrap(d, title, f, available_width)
        bbox = d.textbbox((0, 0), 'Ág', font=f)
        height = bbox[3] - bbox[1] + 13
        if len(lines) <= 6 and len(lines) * height <= 370:
            break
    y = 890
    for line in lines:
        d.text((51, y), line, font=f, fill='white', stroke_width=1, stroke_fill='#24102C')
        y += height
    d.rectangle((51, 1286, 1029, 1292), fill='#F59D00')
    d.text((51, 1301), 'ACESSE A NOTÍCIA PELO SITE  •  DFESPORTES.COM', font=font(21, True), fill='white')
    filename.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert('RGB').save(filename, 'PNG', optimize=True)


def telegram_photo(token, chat_id, item, path):
    caption = f"🚨 NOVA MATÉRIA — DF ESPORTES\n\n📰 {item['title']}\n\n{item['lead']}\n\n📲 Leia a matéria completa no DF Esportes. Link na bio.\n🔗 {item['link']}"
    if item['credit']:
        caption += f"\n📷 {item['credit']}"
    # Telegram limita legenda de foto; envia texto separadamente para não truncar o lead.
    boundary = '----DFEsportesBoundary85024'
    data = path.read_bytes()
    parts = []
    for k, v in [('chat_id', chat_id)]:
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.extend([f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="arte.png"\r\nContent-Type: image/png\r\n\r\n'.encode(), data, b'\r\n', f'--{boundary}--\r\n'.encode()])
    req = urllib.request.Request(f'https://api.telegram.org/bot{token}/sendPhoto', data=b''.join(parts), headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
    with urllib.request.urlopen(req, timeout=50) as r:
        response = json.load(r)
        if not response.get('ok'):
            raise RuntimeError(str(response))
    # Mensagem de texto completa, separada da foto.
    payload = urllib.parse.urlencode({'chat_id': chat_id, 'text': caption}).encode()
    req = urllib.request.Request(f'https://api.telegram.org/bot{token}/sendMessage', data=payload)
    with urllib.request.urlopen(req, timeout=40) as r:
        response = json.load(r)
        if not response.get('ok'):
            raise RuntimeError(str(response))


def main():
    test = os.getenv('TEST_MODE', '').lower() == 'true'
    items = read_feed(fetch(FEED))
    if not items:
        raise RuntimeError('RSS retornou zero matérias')
    old = json.loads(STATE.read_text()) if STATE.exists() else {'ids': []}
    seen = set(old['ids'])
    token = os.environ['TELEGRAM_BOT_TOKEN']
    chat = os.environ['TELEGRAM_CHAT_ID']
    if not test and not STATE.exists():
        STATE.write_text(json.dumps({'ids': [i['id'] for i in items]}, ensure_ascii=False, indent=2) + '\n')
        print('Primeira execução: matérias existentes registradas, sem envio.')
        return
    selected = list(reversed(items[:2])) if test else [i for i in reversed(items) if i['id'] not in seen]
    if not selected:
        print('Nenhuma matéria nova.')
        return
    for idx, item in enumerate(selected):
        print('Processando:', item['title'])
        filename = OUTPUT / f'arte_{idx}.png'
        art(item, filename)
        telegram_photo(token, chat, item, filename)
        print('Enviado:', item['link'])
    if not test:
        # Atualiza estado somente após todos os envios bem-sucedidos.
        merged = [i['id'] for i in items] + [i for i in old['ids'] if i not in {x['id'] for x in items}]
        STATE.write_text(json.dumps({'ids': merged[:200]}, ensure_ascii=False, indent=2) + '\n')

if __name__ == '__main__':
    main()
