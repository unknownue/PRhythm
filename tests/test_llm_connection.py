"""
LLM connection test module for PRhythm system.
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not available, continue with existing environment
    pass

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from agents.configuration import AgentConfiguration


def _get_model_name_for_provider(provider):
    """Get full model name for a given provider type."""
    provider_lower = provider.lower()
    
    if provider_lower == "openai":
        model = os.getenv("PUB_OPENAI_MODEL", "gpt-4")
        return f"openai:{model}"
    elif provider_lower == "anthropic":
        model = os.getenv("PUB_ANTHROPIC_MODEL", "claude-3-sonnet")
        return f"anthropic:{model}"
    elif provider_lower == "google":
        model = os.getenv("PUB_GOOGLE_MODEL", "gemini-pro")
        return f"google:{model}"
    elif provider_lower == "ollama":
        model = os.getenv("PUB_OLLAMA_SERVER_MODEL", "qwen:4b")
        return f"ollama:{model}"
    else:
        return None


def test_llm_connection(model_override=None):
    """Test basic LLM connection with a simple 'hello world' message.
    
    Args:
        model_override: Optional provider type (openai, anthropic, google, llama) to override default
    """
    
    print("Starting LLM connection test...")
    
    try:
        # Load configuration from environment variables
        config = AgentConfiguration.from_runnable_config()
        
        # Determine model name based on provider type
        if model_override:
            model_name = _get_model_name_for_provider(model_override)
            if not model_name:
                print(f"❌ Error: Unknown provider '{model_override}' or missing model configuration")
                return False
        else:
            model_name = config.analysis_model
            
        max_tokens = config.analysis_max_tokens
        
        print(f"Using model: {model_name}")
        print(f"Max tokens: {max_tokens}")
        
        # Get API key
        api_key = config.get_api_key_for_model(model_name)
        
        # For Ollama models, API key can be empty or None
        if model_name.startswith("ollama:"):
            if api_key is None:
                api_key = ""  # Use empty string for Ollama if not set
            print(f"✓ Ollama server configuration (API key: {'set' if api_key else 'empty'})")
        else:
            # For other models, API key is required
            if not api_key:
                print("❌ Error: API key not found")
                print("Please set the appropriate environment variable:")
                if model_name.startswith("openai:"):
                    print("  export PUB_OPENAI_API_KEY=your_key_here")
                elif model_name.startswith("anthropic:"):
                    print("  export PUB_ANTHROPIC_API_KEY=your_key_here")
                elif model_name.startswith(("google:", "gemini:")):
                    print("  export PUB_GOOGLE_API_KEY=your_key_here")
                return False
            
            print(f"✓ API key configured (length: {len(api_key)} characters)")
        
        # Initialize model
        print("Initializing model...")
        
        # Special handling for Ollama server
        if model_name.startswith("ollama:"):
            # Get Ollama server configuration
            ollama_config = config.get_ollama_server_config()
            base_url = ollama_config.get("base_url")
            actual_model = ollama_config.get("model", "qwen:4b")
            
            if not base_url:
                print("❌ Error: PUB_OLLAMA_SERVER_BASE_URL not configured")
                print("Please set: export PUB_OLLAMA_SERVER_BASE_URL=http://localhost:11434")
                return False
            
            print(f"Ollama server URL: {base_url}")
            print(f"Ollama model: {actual_model}")
            
            # First, check if the model exists
            import requests
            try:
                tags_response = requests.get(f"{base_url}/api/tags", timeout=10)
                if tags_response.status_code == 200:
                    models_data = tags_response.json()
                    available_models = [model.get('name', '') for model in models_data.get('models', [])]
                    print(f"Available models: {available_models}")
                    
                    if actual_model not in available_models:
                        print(f"❌ Error: Model '{actual_model}' not found in Ollama")
                        print(f"Available models: {', '.join(available_models) if available_models else 'None'}")
                        return False
                else:
                    print(f"⚠️  Warning: Could not check available models (HTTP {tags_response.status_code})")
            except Exception as e:
                print(f"⚠️  Warning: Could not check available models: {str(e)}")
            
            # Use official LangChain Ollama integration
            print("Testing with LangChain Ollama...")
            try:
                from langchain_ollama import ChatOllama
                from urllib.parse import urlparse
                
                # Parse base URL to get host and port
                parsed_url = urlparse(base_url)
                host = parsed_url.hostname
                port = parsed_url.port
                
                # Initialize ChatOllama with correct parameters
                model = ChatOllama(
                    model=actual_model,
                    base_url=base_url,
                    # host=host,
                    # port=port,
                    timeout=120
                )
                
                print("✓ LangChain Ollama model initialized")
                
                # Test with a simple message
                response = model.invoke("hello world")
                
                if response and response.content:
                    print(f"✓ Received response: {response.content[:100]}...")
                    print("✅ LangChain Ollama connection test successful!")
                    return True
                else:
                    print("❌ Error: Received empty response")
                    return False
                    
            except Exception as e:
                print(f"❌ LangChain Ollama test failed: {str(e)}")
                print("Falling back to direct API call...")
                
                # Fallback to direct API call
                try:
                    import requests
                    response = requests.post(
                        f"{base_url}/v1/chat/completions",
                        headers={"Content-Type": "application/json"},
                        json={
                            "model": actual_model,
                            "messages": [{"role": "user", "content": "hello world"}],
                            "max_tokens": 10
                        },
                        timeout=30
                    )
                    if response.status_code == 200:
                        result = response.json()
                        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                        print(f"✓ Direct API fallback successful: {content}")
                        print("✅ Ollama connection test successful!")
                        return True
                    else:
                        print(f"❌ Direct API test failed: HTTP {response.status_code}")
                        return False
                except Exception as e2:
                    print(f"❌ Direct API test also failed: {str(e2)}")
                    return False
        else:
            # Standard model initialization
            model = init_chat_model(
                model=model_name,
                max_tokens=max_tokens,
                api_key=api_key
            )
        
        print("✓ Model initialization successful")
        
        # Test basic connection with hello world message
        print("Sending test message: 'hello world'")
        test_message = HumanMessage(content="hello world")
        
        # Make the API call
        response = model.invoke([test_message])
        
        if response and response.content:
            print(f"✓ Received response: {response.content[:100]}...")
            print("✅ LLM connection test successful!")
            return True
        else:
            print("❌ Error: Received empty response")
            return False
            
    except Exception as e:
        print(f"❌ LLM connection test failed: {str(e)}")
        return False


if __name__ == "__main__":
    # Run test directly
    success = test_llm_connection()
    sys.exit(0 if success else 1)