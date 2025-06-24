from strands import Agent

def test_bedrock():
    from strands.models import BedrockModel

    bedrock_model = BedrockModel(
        model_id= "us.amazon.nova-premier-v1:0",
        params={"max_tokens": 1600, "temperature": 0.7}
    )
    agent = Agent(model=bedrock_model,
                system_prompt="You are a helpful assistant.")
    response = agent("Tell me about Bedrock")
    assert response is not None

    bedrock_model2 = BedrockModel(
        model="us.anthropic.claude-3-7-sonnet-20250219-v1:0"
    )
    agent2 = Agent(model=bedrock_model2,
                system_prompt="You are a helpful assistant.")
    response2 = agent2("Tell me about Bedrock")
    assert response2 is not None

def test_litellm():
    from strands.models.litellm import LiteLLMModel

    litellm_model = LiteLLMModel(
        model_id= "azure/gpt-4o-mini",     
        params={"max_tokens": 1600, 
                "temperature": 0.7}
    )
    agent = Agent(model=litellm_model)
    response = agent("Tell me about LiteLLM")
    assert response is not None

def test_ollama():
    from strands.models.ollama import OllamaModel

    ollama_model = OllamaModel(
        model_id= "XXXXXX",
        host="http://localhost:11434",
        params={"max_tokens": 1600,
                "temperature": 0.7}
    )
    agent = Agent(model=ollama_model)
    response = agent("Tell me about Ollama")
    assert response is not None

if __name__ == "__main__":
    test_bedrock()
