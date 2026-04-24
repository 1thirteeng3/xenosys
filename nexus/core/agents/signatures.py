import dspy

class ExtractKnowledgeGraph(dspy.Signature):
    """
    Analise a interação entre o Usuário e o Agente. 
    Se houver qualquer informação permanente (preferências do usuário, restrições operacionais, 
    fatos novos importantes sobre o sistema ou sobre o usuário), extraia-os como Entidades e Relações.
    Se não houver nada de permanente/relevante a ser aprendido, retorne listas vazias.
    """
    user_input = dspy.InputField(desc="O comando ou mensagem do usuário")
    agent_response = dspy.InputField(desc="A resposta fornecida pelo agente")
    
    # DSPy forçará a saída neste formato exato (Lista de dicionários JSON-like)
    entities = dspy.OutputField(desc="Lista de entidades. Ex: [{'name': 'Usuário', 'type': 'Person'}, {'name': 'Modo Escuro', 'type': 'Preference'}]")
    relations = dspy.OutputField(desc="Lista de relações. Ex: [{'source': 'Usuário', 'target': 'Modo Escuro', 'relation': 'prefere'}]")
