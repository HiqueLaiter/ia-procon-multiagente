"""
IA PROCON - interface de chat simples (navegador).

Uso:   python chat_web.py        e abra  http://127.0.0.1:8000
Usa só a biblioteca padrão do Python (sem instalar nada novo) e chama app.analisar().
Cada mensagem é tratada como uma NOVA reclamação (o sistema não guarda histórico de conversa).
"""
import json
import os
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import app

ROTULOS = {"triagem": "Triagista", "pesquisa": "Pesquisador Jurídico",
           "auditoria": "Auditor", "redacao": "Redator"}
ORDEM = ("triagem", "pesquisa", "auditoria", "redacao")
TRABALHOS = {}            # id -> estado
TRAVA = threading.Lock()  # um trabalho por vez (limite de chamadas da API gratuita)


def modelo_do(agente):
    """Mesmo critério do app.criar_llm: variável por agente, senão o modelo padrão."""
    return os.environ.get(f"IA_PROCON_MODELO_{agente.upper()}") or app.MODELO


def rodar(id_):
    estado = TRABALHOS[id_]
    marca = {"t": time.perf_counter()}

    def etapa(agente, texto=""):
        agora = time.perf_counter()
        estado["etapas"][agente] = {"segundos": round(agora - marca["t"], 1), "saida": texto}
        marca["t"] = agora
        estado["feitas"].append(agente)

    try:
        resposta, avisos = app.analisar(estado["texto"], etapa=etapa)
        estado.update(resposta=resposta, avisos=avisos)
    except BaseException as erro:  # inclui SystemExit de erros de configuração (ex.: chave ausente)
        estado["erro"] = str(erro) or erro.__class__.__name__
    finally:
        estado["pronto"] = True
        TRAVA.release()


PAGINA = """<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>IA PROCON</title>
<style>
body{font-family:system-ui,sans-serif;background:#eef1f5;margin:0;display:flex;flex-direction:column;height:100vh}
header{background:#0b3d91;color:#fff;padding:14px 20px}header small{opacity:.8;display:block}
#chat{flex:1;overflow:auto;padding:20px;max-width:860px;width:100%;box-sizing:border-box;margin:auto}
.m{margin:10px 0;padding:12px 14px;border-radius:12px;max-width:85%;white-space:pre-wrap;line-height:1.45}
.u{background:#0b3d91;color:#fff;margin-left:auto}.b{background:#fff;border:1px solid #d5dae1}
.s{color:#555;font-style:italic;background:none;border:none}
details{margin-top:8px;font-size:.9em;color:#7a4b00}
.eq{background:#fff;border:1px solid #d5dae1;border-radius:12px;padding:10px 14px;max-width:85%;margin:10px 0}
.eq details{color:#222;margin:6px 0;border-left:4px solid #ccc;padding-left:8px}
.eq details.f{border-color:#2e9e4f}.eq details.a{border-color:#e0a000}
.eq summary{cursor:pointer}.eq pre{white-space:pre-wrap;font:inherit;background:#f6f8fa;padding:8px;border-radius:6px;max-height:320px;overflow:auto}
.eq small{color:#666}
form{display:flex;gap:8px;padding:12px 20px;background:#fff;border-top:1px solid #d5dae1}
textarea{flex:1;padding:10px;border-radius:8px;border:1px solid #bbb;font:inherit;height:70px;resize:none}
button{background:#0b3d91;color:#fff;border:0;border-radius:8px;padding:0 22px;font:inherit;cursor:pointer}
button:disabled{opacity:.5}
</style>
<header><b>IA PROCON</b><small>Protótipo acadêmico: não é orientação jurídica oficial</small></header>
<div id="chat"><div class="m b">Olá! Descreva sua reclamação de consumo (o que comprou, quando, o que aconteceu e o que a empresa respondeu) e eu analiso com base no Código de Defesa do Consumidor.</div></div>
<form id="f"><textarea id="t" placeholder="Descreva a sua reclamação..."></textarea><button id="b">Enviar</button></form>
<script>
const chat=document.getElementById('chat'),t=document.getElementById('t'),b=document.getElementById('b');
function add(c,txt){const d=document.createElement('div');d.className='m '+c;d.textContent=txt;chat.appendChild(d);chat.scrollTop=1e9;return d}
document.getElementById('f').onsubmit=async e=>{
 e.preventDefault();const txt=t.value.trim();if(!txt)return;t.value='';b.disabled=true;add('u',txt);
 const st=add('s','Enviando...');
 try{
  const r=await fetch('/enviar',{method:'POST',body:JSON.stringify({texto:txt})});const j=await r.json();
  if(j.erro){st.textContent=j.erro;b.disabled=false;return}
  st.remove();
  const painel=document.createElement('div');painel.className='eq';
  painel.innerHTML='<b>Equipe de agentes trabalhando</b><br><small>Clique em cada etapa concluída para ver o que o agente produziu.</small>';
  chat.appendChild(painel);const itens={};
  const iv=setInterval(async()=>{
   const s=await (await fetch('/status?id='+j.id)).json();
   s.etapas.forEach(e=>{
    let it=itens[e.agente];
    if(!it){const d=document.createElement('details');const sm=document.createElement('summary');const pre=document.createElement('pre');
     d.appendChild(sm);d.appendChild(pre);painel.appendChild(d);it=itens[e.agente]={d,sm,pre,estado:''};}
    const est=e.estado+e.segundos;
    if(it.estado!==est){it.estado=est;
     it.d.className=e.estado==='feito'?'f':(e.estado==='trabalhando'?'a':'');
     const icone=e.estado==='feito'?'✔ ':(e.estado==='trabalhando'?'⏳ ':'… ');
     it.sm.textContent=icone+e.rotulo+' ('+e.modelo+')'+(e.estado==='feito'?' - '+e.segundos+' s':(e.estado==='trabalhando'?' - trabalhando...':' - aguardando'));
     it.pre.textContent=e.saida||'(ainda sem saída)';}
   });
   chat.scrollTop=1e9;
   if(!s.pronto)return;
   clearInterval(iv);
   if(s.erro){add('b','Erro: '+s.erro)}else{const d=add('b',s.resposta);
    if(s.avisos.length){const x=document.createElement('details');x.innerHTML='<summary>Verificação automática ('+s.avisos.length+' aviso(s))</summary>';
     const p=document.createElement('div');p.textContent=s.avisos.join('\\n');x.appendChild(p);d.appendChild(x)}}
   b.disabled=false;
  },1500);
 }catch(err){st.textContent='Falha de conexão: '+err;b.disabled=false}
};
</script></html>"""


class Manipulador(BaseHTTPRequestHandler):
    def _json(self, dados, codigo=200):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        if self.path == "/":
            corpo = PAGINA.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
        elif self.path.startswith("/status"):
            e = TRABALHOS.get(self.path.split("id=")[-1])
            if not e:
                return self._json({"erro": "trabalho não encontrado"}, 404)
            etapas, atual = [], None
            for a in ORDEM:
                if a in e["etapas"]:
                    estado = "feito"
                elif atual is None and not e["pronto"]:
                    estado, atual = "trabalhando", a
                else:
                    estado = "aguardando"
                dados = e["etapas"].get(a, {})
                etapas.append({"agente": a, "rotulo": ROTULOS[a], "modelo": modelo_do(a), "estado": estado,
                               "segundos": dados.get("segundos", 0), "saida": dados.get("saida", "")})
            self._json({"pronto": e["pronto"], "etapas": etapas,
                        "resposta": e.get("resposta"), "avisos": e.get("avisos", []), "erro": e.get("erro")})
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/enviar":
            return self.send_error(404)
        tamanho = int(self.headers.get("Content-Length", 0))
        texto = json.loads(self.rfile.read(tamanho) or b"{}").get("texto", "").strip()
        if len(texto) < 20:
            return self._json({"erro": "Descreva a reclamação com um pouco mais de detalhes."})
        if not TRAVA.acquire(blocking=False):
            return self._json({"erro": "Já existe uma análise em andamento. Aguarde terminar."})
        id_ = uuid.uuid4().hex
        TRABALHOS[id_] = {"texto": texto, "feitas": [], "etapas": {}, "pronto": False}
        threading.Thread(target=rodar, args=(id_,), daemon=True).start()
        self._json({"id": id_})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print("IA PROCON (chat) em http://127.0.0.1:8000  - Ctrl+C para encerrar")
    ThreadingHTTPServer(("127.0.0.1", 8000), Manipulador).serve_forever()
