import streamlit as st
from datetime import datetime
import logging
from dataclasses import dataclass
from typing import List, Optional
from langchain_ollama import OllamaLLM
from langchain.schema import SystemMessage, HumanMessage, AIMessage
import json
from resources.dietary_data import DIETARY_RESTRICTIONS
# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class UserProfile:
    name: str
    dietary_restrictions: List[str]
    additional_notes: Optional[str] = None
    

class DietaryAssistant:

    def __init__(self):
        self.setup_page_config()
        self.initialize_session_state()
        self.DIETARY_RESTRICTIONS = DIETARY_RESTRICTIONS  # Access the imported dictionary

    @staticmethod
    def setup_page_config():
        st.set_page_config(
            page_title="Assistente de Restrições Alimentares",
            page_icon="🥗",
            layout="wide",
            initial_sidebar_state="expanded"
        )

    def initialize_session_state(self):
        default_states = {
            'onboarding_complete': False,
            'user_profile': None,
            'messages': [],
            'processing_message': False,
            'chat_history': []
        }
        
        for key, default_value in default_states.items():
            if key not in st.session_state:
                st.session_state[key] = default_value

    def create_system_prompt(self, user_profile: UserProfile) -> SystemMessage:
        return SystemMessage(content=f"""Você é um assistente especializado em restrições alimentares, 
        conversando com {user_profile.name}. 
        
        Restrições alimentares do usuário:
        {self._format_restrictions(user_profile.dietary_restrictions)}
        
        Observações adicionais:
        {user_profile.additional_notes or 'Nenhuma observação adicional.'}
        
        Diretrizes:
        1. Personalize todas as respostas considerando as restrições específicas.
        2. Forneça informações detalhadas sobre substituições seguras de ingredientes.
        3. Alerte sobre riscos de contaminação cruzada quando relevante.
        4. Sugira alternativas nutricionalmente equivalentes quando possível.
        5. Recomende consulta a profissionais de saúde para casos específicos.
        6. Mantenha um tom amigável e empático, reconhecendo os desafios das restrições alimentares.
        
        Formato das respostas:
        - Inicie com um cumprimento personalizado
        - Forneça a informação principal de forma clara
        - Adicione alertas de segurança quando necessário
        - Conclua com sugestões práticas quando apropriado""")

    def _format_restrictions(self, restrictions: List[str]) -> str:
        formatted = []
        for r in restrictions:
            if r in self.DIETARY_RESTRICTIONS:
                info = self.DIETARY_RESTRICTIONS[r]
                formatted.append(f"- {r}:\n  Descrição: {info['description']}\n  "
                               f"Ingredientes comuns para evitar: {', '.join(info['common_ingredients'])}")
            else:
                formatted.append(f"- {r}")
        return "\n".join(formatted)

    def show_onboarding(self):
        st.title("🥗 Bem-vindo ao Assistente de Restrições Alimentares")
        
        with st.form("onboarding_form", clear_on_submit=True):
            col1, col2 = st.columns([1, 1])
            
            with col1:
                user_name = st.text_input(
                    "Como você gostaria de ser chamado?",
                    key="name_input"
                )
                
                dietary_restrictions = st.multiselect(
                    "Selecione suas restrições alimentares:",
                    options=list(self.DIETARY_RESTRICTIONS.keys()) + ["Outra"],
                    help="Você pode selecionar múltiplas opções"
                )

            with col2:
                if "Outra" in dietary_restrictions:
                    other_restriction = st.text_input(
                        "Especifique sua restrição alimentar:",
                        key="other_restriction"
                    )
                
                additional_notes = st.text_area(
                    "Observações adicionais",
                    help="Informe qualquer detalhe adicional sobre suas restrições ou preferências"
                )

            submit_button = st.form_submit_button("Começar", use_container_width=True)
            
            if submit_button:
                if not user_name or not dietary_restrictions:
                    st.error("Por favor, preencha seu nome e selecione ao menos uma restrição alimentar.")
                    return

                # Processa restrições personalizadas
                final_restrictions = [r for r in dietary_restrictions if r != "Outra"]
                if "Outra" in dietary_restrictions and other_restriction:
                    final_restrictions.append(other_restriction)

                # Cria perfil do usuário
                user_profile = UserProfile(
                    name=user_name,
                    dietary_restrictions=final_restrictions,
                    additional_notes=additional_notes
                )

                # Atualiza estado da sessão
                st.session_state.user_profile = user_profile
                st.session_state.onboarding_complete = True
                st.session_state.messages = [self.create_system_prompt(user_profile)]
                
                # Salva perfil no histórico
                self.save_user_profile(user_profile)
                
                st.rerun()

    def show_chat_interface(self):
        # Container principal
        main_container = st.container()
        
        # Sidebar com informações do usuário e recursos
        with st.sidebar:
            self.show_user_info()
            self.show_helpful_resources()
        
        # Container principal para chat
        with main_container:
            st.title(f"🥗 Olá, {st.session_state.user_profile.name}!")
            
            # Área de mensagens
            self.display_chat_messages()
            
            # Input de chat (fora de qualquer container)
            self.handle_user_input()

    def display_chat_messages(self):
        messages_container = st.container()
        with messages_container:
            for message in st.session_state.messages[1:]:  # Skip system message
                if isinstance(message, HumanMessage):
                    with st.chat_message("user"):
                        st.markdown(message.content)
                elif isinstance(message, AIMessage):
                    with st.chat_message("assistant"):
                        st.markdown(message.content)

    def handle_user_input(self):
        # Chat input deve estar no nível principal, fora de qualquer container
        if prompt := st.chat_input("Digite sua pergunta sobre restrições alimentares:"):
            if not st.session_state.processing_message:
                st.session_state.processing_message = True
                
                try:
                    # Adiciona mensagem do usuário
                    st.session_state.messages.append(HumanMessage(content=prompt))
                    
                    # Obtém resposta do LLM
                    with st.spinner("Processando sua pergunta..."):
                        response = self.get_assistant_response(prompt)
                        if response:
                            st.session_state.messages.append(AIMessage(content=response))
                            self.save_chat_history()
                
                except Exception as e:
                    logger.error(f"Erro ao processar mensagem: {str(e)}")
                    st.error("Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente.")
                
                finally:
                    st.session_state.processing_message = False
                    st.rerun()

    def show_user_info(self):
        st.subheader("📋 Seu Perfil")
        user = st.session_state.user_profile
        
        with st.expander("Suas Informações", expanded=True):
            st.write(f"**Nome:** {user.name}")
            st.write("**Restrições Alimentares:**")
            for restriction in user.dietary_restrictions:
                st.write(f"- {restriction}")
            
            if user.additional_notes:
                st.write("**Observações:**")
                st.write(user.additional_notes)
        
        if st.button("✏️ Modificar Informações"):
            st.session_state.clear()
            st.rerun()

    def show_helpful_resources(self):
        st.subheader("📚 Recursos Úteis")
        
        with st.expander("Dicas de Segurança", expanded=False):
            st.markdown("""
            - Sempre leia os rótulos dos alimentos
            - Informe suas restrições em restaurantes
            - Tenha cuidado com contaminação cruzada
            - Mantenha um diário alimentar
            """)
        
        with st.expander("Links Úteis", expanded=False):
            st.markdown("""
            - [Anvisa - Rotulagem de Alimentos](https://www.gov.br/anvisa)
            - [Sociedade Brasileira de Alimentação e Nutrição](https://sban.org.br)
            - [Associação Brasileira de Alergia e Imunologia](https://asbai.org.br)
            """)
        
        st.warning("""⚠️ **Importante:** As informações fornecidas são apenas para orientação geral. 
        Sempre consulte profissionais de saúde para recomendações personalizadas.""")

    def get_assistant_response(self, prompt: str) -> Optional[str]:
        try:
            llm = OllamaLLM(
                model="llama3.1",
                temperature=0.2,
            )
            
            # Prepara mensagens para contexto
            context = "\n".join([msg.content for msg in st.session_state.messages])
            context += f"\nUsuário: {prompt}"
            
            # Obtém resposta
            response = llm.invoke(context)
            return response
        
        except Exception as e:
            logger.error(f"Erro ao obter resposta do LLM: {str(e)}")
            return None

    def save_chat_history(self):
        try:
            history = {
                'timestamp': datetime.now().isoformat(),
                'user_profile': {
                    'name': st.session_state.user_profile.name,
                    'restrictions': st.session_state.user_profile.dietary_restrictions,
                    'notes': st.session_state.user_profile.additional_notes
                },
                'messages': [(type(msg).__name__, msg.content) for msg in st.session_state.messages]
            }
            
            st.session_state.chat_history.append(history)
            
        except Exception as e:
            logger.error(f"Erro ao salvar histórico: {str(e)}")

    def save_user_profile(self, profile: UserProfile):
        try:
            profile_data = {
                'timestamp': datetime.now().isoformat(),
                'name': profile.name,
                'restrictions': profile.dietary_restrictions,
                'notes': profile.additional_notes
            }
            
            # Aqui você pode implementar a persistência em banco de dados ou arquivo
            logger.info(f"Perfil salvo: {json.dumps(profile_data, ensure_ascii=False)}")
            
        except Exception as e:
            logger.error(f"Erro ao salvar perfil: {str(e)}")

def main():
    assistant = DietaryAssistant()
    
    if not st.session_state.onboarding_complete:
        assistant.show_onboarding()
    else:
        assistant.show_chat_interface()

if __name__ == "__main__":
    main()