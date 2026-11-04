"""Interface web (Streamlit) do atendente da Empório da Música.

    uv run streamlit run app.py

Usa a mesma classe Agent e a mesma persistência em sessions/ da CLI. Cada resposta
traz um bloco expansível com as ferramentas consultadas, para dar visibilidade de
quando o agente foi aos dados e quando foi às políticas.
"""

from __future__ import annotations

import json

import streamlit as st
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from emporio_agent.agent import Agent, provider_error_text
from emporio_agent.config import model_name, provider, reference_now
from emporio_agent.memory import SessionStore

st.set_page_config(page_title="Empório da Música", page_icon="🎸", layout="centered")


@st.cache_resource(show_spinner="Carregando o agente...")
def get_agent() -> Agent:
    return Agent()


@st.cache_resource
def get_store() -> SessionStore:
    return SessionStore()


def _render_text(text: str) -> None:
    """Mostra a resposta preservando as quebras de linha.

    O agente escreve texto puro, um produto por linha. O Markdown do Streamlit
    juntaria essas linhas em um parágrafo (dois espaços antes da quebra forçam a
    quebra) e trataria o trecho entre dois cifrões como fórmula matemática,
    sumindo com o "R$" dos preços (o cifrão precisa ser escapado).
    """
    st.markdown(text.replace("$", "\\$").replace("\n", "  \n"))


def _render_tools(calls: list[dict]) -> None:
    if not calls:
        return
    with st.expander(f"Ferramentas consultadas ({len(calls)})"):
        for call in calls:
            st.markdown(f"**{call['name']}**")
            st.code(json.dumps(call["args"], ensure_ascii=False), language="json")
            if call.get("result"):
                try:
                    st.json(json.loads(call["result"]), expanded=False)
                except (json.JSONDecodeError, TypeError):
                    st.text(call["result"][:2000])


def _render_history(messages: list[BaseMessage]) -> None:
    """Reconstrói o chat a partir das mensagens salvas, agrupando as chamadas de
    ferramenta que antecedem cada resposta final."""
    pending: dict[str, dict] = {}
    for msg in messages:
        if isinstance(msg, HumanMessage):
            with st.chat_message("user"):
                st.write(msg.content)
        elif isinstance(msg, ToolMessage):
            if msg.tool_call_id in pending:
                pending[msg.tool_call_id]["result"] = msg.content
        elif isinstance(msg, AIMessage):
            for call in msg.tool_calls:
                pending[call["id"]] = {"name": call["name"], "args": call["args"], "result": ""}
            text = (msg.text or "").strip()
            if text:
                with st.chat_message("assistant"):
                    _render_tools(list(pending.values()))
                    _render_text(text)
                pending = {}


# ---- barra lateral -----------------------------------------------------------

with st.sidebar:
    st.title("Empório da Música")
    st.caption("Sua música começa aqui.")
    session_id = st.text_input("Sessão (ex.: telefone do cliente)", value="web")
    if st.button("Nova conversa", use_container_width=True):
        get_store().delete(session_id)
        st.rerun()
    st.divider()
    st.markdown(
        f"**Provedor:** {provider()}  \n"
        f"**Modelo:** {model_name()}  \n"
        f"**Data de referência:** {reference_now():%d/%m/%Y}"
    )
    st.caption(
        "O agente consulta o catálogo, os pedidos e o manual de políticas antes de "
        "responder. Abra 'Ferramentas consultadas' em cada resposta para ver o que foi usado."
    )

# ---- chat --------------------------------------------------------------------

store = get_store()
history = store.load(session_id)

if not history:
    with st.chat_message("assistant"):
        st.write(
            "Oi! Sou o atendente virtual da Empório da Música. Posso ajudar com produtos, "
            "preços, pedidos, trocas e informações da loja. Como posso ajudar?"
        )

_render_history(history)

if prompt := st.chat_input("Escreva sua mensagem..."):
    with st.chat_message("user"):
        st.write(prompt)
    with st.chat_message("assistant"):
        try:
            with st.spinner("Consultando..."):
                reply = get_agent().reply(history, prompt)
        except Exception as exc:  # noqa: BLE001 - erro do provedor vira aviso na tela
            st.warning(provider_error_text(exc))
        else:
            store.append(session_id, reply.new_messages)
            _render_tools(
                [{"name": t.name, "args": t.args, "result": t.result} for t in reply.tool_calls]
            )
            _render_text(reply.text)
