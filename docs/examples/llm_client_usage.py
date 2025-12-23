"""
LLM Client Usage Examples

This file demonstrates how to use the OllamaClient for various tasks.
"""

import asyncio
import logging
from pathlib import Path
import yaml

from orchestrator import OllamaClient, OllamaConnectionError, OllamaModelNotFoundError


# Configure logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def example_basic_generation():
    """Example 1: Basic text generation"""
    print("\n=== Example 1: Basic Text Generation ===\n")
    
    async with OllamaClient() as client:
        # Check if service is healthy
        if not await client.health_check():
            print("Ollama service is not available!")
            return
            
        # Simple generation
        response = await client.generate(
            model="qwen2.5-coder:14b-instruct-q4_K_M",
            prompt="Write a Python function to calculate factorial",
            temperature=0.7
        )
        
        print(f"Generated text:\n{response.text}\n")
        print(f"Model used: {response.model}")
        print(f"Tokens generated: {response.eval_count}")


async def example_streaming_generation():
    """Example 2: Streaming text generation"""
    print("\n=== Example 2: Streaming Generation ===\n")
    
    async with OllamaClient() as client:
        # Generate with streaming for real-time output
        stream = await client.generate(
            model="qwen2.5-coder:14b-instruct-q4_K_M",
            prompt="Explain asyncio in Python in 3 sentences",
            temperature=0.7,
            stream=True
        )
        
        print("Streaming response: ", end='', flush=True)
        async for chunk in stream:
            print(chunk, end='', flush=True)
        print("\n")


async def example_system_prompt():
    """Example 3: Using system prompts for specialized behavior"""
    print("\n=== Example 3: System Prompts ===\n")
    
    async with OllamaClient() as client:
        response = await client.generate(
            model="qwen2.5-coder:14b-instruct-q4_K_M",
            prompt="How do I sort a list?",
            system="You are a Python expert who always provides complete, working code examples with comments.",
            temperature=0.5
        )
        
        print(f"Response with system prompt:\n{response.text}\n")


async def example_embeddings():
    """Example 4: Generating embeddings"""
    print("\n=== Example 4: Text Embeddings ===\n")
    
    async with OllamaClient() as client:
        # Single text embedding
        response = await client.embed(
            model="nomic-embed-text",
            input="This is a test sentence for embedding"
        )
        
        print(f"Embedding dimension: {len(response.embeddings[0])}")
        print(f"First 10 values: {response.embeddings[0][:10]}")
        
        # Batch embeddings
        texts = [
            "Python is a programming language",
            "JavaScript is used for web development",
            "Machine learning uses neural networks"
        ]
        
        batch_response = await client.embed(
            model="nomic-embed-text",
            input=texts
        )
        
        print(f"\nGenerated {len(batch_response.embeddings)} embeddings")
        print(f"Each with dimension: {len(batch_response.embeddings[0])}")


async def example_error_handling():
    """Example 5: Proper error handling"""
    print("\n=== Example 5: Error Handling ===\n")
    
    async with OllamaClient() as client:
        try:
            # Try to use a model that doesn't exist
            response = await client.generate(
                model="nonexistent-model:latest",
                prompt="Hello"
            )
        except OllamaModelNotFoundError as e:
            print(f"Model not found: {e}")
            print("Suggested action: Run 'ollama pull <model-name>'")
            
        try:
            # Try with wrong host (simulating connection error)
            bad_client = OllamaClient(host="http://localhost:9999")
            async with bad_client:
                await bad_client.generate(
                    model="qwen2.5-coder:14b-instruct-q4_K_M",
                    prompt="Hello"
                )
        except OllamaConnectionError as e:
            print(f"\nConnection error: {e}")
            print("Make sure Ollama service is running")


async def example_fallback_models():
    """Example 6: Using fallback models for resilience"""
    print("\n=== Example 6: Fallback Models ===\n")
    
    async with OllamaClient() as client:
        # Try primary model, fall back to alternatives if unavailable
        response = await client.generate_with_fallback(
            model="qwen2.5-coder:14b-instruct-q4_K_M",
            prompt="Write a hello world in Python",
            fallback_models=[
                "qwen2.5-coder:7b-instruct-q4_K_M",
                "deepseek-coder:6.7b-instruct-q4_K_M"
            ],
            temperature=0.7
        )
        
        print(f"Response from model {response.model}:\n{response.text}\n")


async def example_model_management():
    """Example 7: Checking and managing models"""
    print("\n=== Example 7: Model Management ===\n")
    
    async with OllamaClient() as client:
        # List all available models
        models = await client.list_models()
        print(f"Available models: {models}\n")
        
        # Check if specific model is available
        model_name = "qwen2.5-coder:14b-instruct-q4_K_M"
        is_available = await client.check_model(model_name)
        print(f"Model '{model_name}' available: {is_available}\n")
        
        # Get model information
        model_info = await client.get_model_info(model_name)
        if model_info:
            print(f"Model info: {model_info.get('size', 'N/A')} bytes")


async def example_load_config():
    """Example 8: Loading configuration from models.yaml"""
    print("\n=== Example 8: Configuration-Based Usage ===\n")
    
    # Load configuration
    config_path = Path("C:/Users/jacob/Documents/Agent Orchestrator/config/models.yaml")
    
    if not config_path.exists():
        print("Config file not found!")
        return
        
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Extract connection settings
    ollama_config = config.get('ollama', {})
    
    # Initialize client with config
    async with OllamaClient(
        host=ollama_config.get('host', 'http://localhost:11434'),
        timeout=ollama_config.get('timeout', 300),
        max_retries=ollama_config.get('max_retries', 3),
    ) as client:
        # Use planner model configuration
        planner_config = config['primary_models']['planner']
        
        response = await client.generate(
            model=planner_config['name'],
            prompt="Plan a simple REST API project",
            system=planner_config['system_prompt'],
            temperature=planner_config['temperature'],
            max_tokens=planner_config['max_tokens']
        )
        
        print(f"Using {planner_config['purpose']}:")
        print(f"{response.text[:200]}...\n")


async def example_metrics():
    """Example 9: Monitoring performance metrics"""
    print("\n=== Example 9: Performance Metrics ===\n")
    
    async with OllamaClient() as client:
        model = "qwen2.5-coder:14b-instruct-q4_K_M"
        
        # Make several requests
        for i in range(3):
            await client.generate(
                model=model,
                prompt=f"Write a comment explaining what {i+1} + {i+1} equals",
                temperature=0.7
            )
        
        # Get metrics
        metrics = client.get_metrics(model)
        model_metrics = metrics[model]
        
        print(f"Metrics for {model}:")
        print(f"  Total requests: {model_metrics.request_count}")
        print(f"  Successful: {model_metrics.success_count}")
        print(f"  Failed: {model_metrics.failure_count}")
        print(f"  Avg latency: {model_metrics.total_latency / max(model_metrics.success_count, 1):.2f}s")


async def example_advanced_parameters():
    """Example 10: Fine-tuning generation parameters"""
    print("\n=== Example 10: Advanced Parameters ===\n")
    
    async with OllamaClient() as client:
        # More focused, deterministic output
        focused_response = await client.generate(
            model="qwen2.5-coder:14b-instruct-q4_K_M",
            prompt="Write a function to check if a number is prime",
            temperature=0.1,      # Very focused
            top_p=0.9,
            top_k=40,
            repeat_penalty=1.2,   # Discourage repetition
            num_ctx=8192,
        )
        
        print("Focused generation (temp=0.1):")
        print(f"{focused_response.text[:300]}...\n")
        
        # More creative output
        creative_response = await client.generate(
            model="qwen2.5-coder:14b-instruct-q4_K_M",
            prompt="Write a function to check if a number is prime",
            temperature=0.9,      # More creative
            top_p=0.95,
        )
        
        print("Creative generation (temp=0.9):")
        print(f"{creative_response.text[:300]}...\n")


async def main():
    """Run all examples"""
    examples = [
        ("Basic Generation", example_basic_generation),
        ("Streaming Generation", example_streaming_generation),
        ("System Prompts", example_system_prompt),
        ("Embeddings", example_embeddings),
        ("Error Handling", example_error_handling),
        ("Fallback Models", example_fallback_models),
        ("Model Management", example_model_management),
        ("Configuration Loading", example_load_config),
        ("Performance Metrics", example_metrics),
        ("Advanced Parameters", example_advanced_parameters),
    ]
    
    print("=" * 60)
    print("LLM Client Usage Examples")
    print("=" * 60)
    
    for i, (name, example_func) in enumerate(examples, 1):
        print(f"\n[{i}/{len(examples)}] Running: {name}")
        try:
            await example_func()
        except Exception as e:
            logger.error(f"Example failed: {e}", exc_info=True)
        
        # Small delay between examples
        await asyncio.sleep(0.5)
    
    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    # Run all examples
    asyncio.run(main())
    
    # Or run individual examples:
    # asyncio.run(example_basic_generation())
    # asyncio.run(example_embeddings())
    # etc.
