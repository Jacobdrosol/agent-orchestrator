"""
Async Ollama Client Wrapper

Provides a high-level async interface to Ollama with health checks, retries, and fallback logic.
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any, AsyncGenerator, Union
from dataclasses import dataclass
import time

try:
    from ollama import AsyncClient
    import httpx
except ImportError:
    raise ImportError(
        "Required packages not installed. Run: pip install ollama httpx"
    )

from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)


# Pydantic models for request/response validation
class GenerateRequest(BaseModel):
    model: str
    prompt: str
    system: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False


class GenerateResponse(BaseModel):
    text: str
    model: str
    total_duration: Optional[float] = None
    load_duration: Optional[float] = None
    prompt_eval_count: Optional[int] = None
    eval_count: Optional[int] = None


class EmbedRequest(BaseModel):
    model: str
    input: Union[str, List[str]]


class EmbedResponse(BaseModel):
    embeddings: List[List[float]]
    model: str


# Custom exceptions
class OllamaConnectionError(Exception):
    """Raised when cannot connect to Ollama service"""
    pass


class OllamaModelNotFoundError(Exception):
    """Raised when requested model is not available"""
    pass


class OllamaGenerationError(Exception):
    """Raised when generation fails"""
    pass


@dataclass
class ModelMetrics:
    """Tracks metrics for a specific model"""
    request_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    total_latency: float = 0.0
    last_success: Optional[float] = None
    last_failure: Optional[float] = None
    circuit_open: bool = False
    circuit_open_until: Optional[float] = None


class OllamaClient:
    """
    Async wrapper around Ollama Python API with retry logic, health checks, and fallback support.
    
    Usage:
        async with OllamaClient() as client:
            response = await client.generate("qwen2.5-coder:14b", "Hello!")
            print(response.text)
    """
    
    def __init__(
        self,
        host: str = "http://localhost:11434",
        timeout: int = 300,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: int = 60,
        health_check_enabled: bool = True,
        health_check_interval: int = 60,
        required_models: Optional[List[str]] = None,
    ):
        """
        Initialize Ollama client.
        
        Args:
            host: Ollama service URL
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Base delay between retries (exponential backoff)
            circuit_breaker_threshold: Consecutive failures before opening circuit
            circuit_breaker_timeout: Seconds to wait before retrying after circuit opens
            health_check_enabled: Enable periodic health checks
            health_check_interval: Seconds between health checks
            required_models: List of models that must be available
        """
        self.host = host
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout
        self.health_check_enabled = health_check_enabled
        self.health_check_interval = health_check_interval
        self.required_models = required_models or []
        
        self._client: Optional[AsyncClient] = None
        self._metrics: Dict[str, ModelMetrics] = {}
        self._health_check_task: Optional[asyncio.Task] = None
        self._is_healthy = False
        
    async def __aenter__(self):
        """Async context manager entry"""
        await self._initialize()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self._cleanup()
        
    async def _initialize(self):
        """Initialize client and run startup health check"""
        self._client = AsyncClient(host=self.host, timeout=self.timeout)
        
        logger.info(f"Initializing Ollama client at {self.host}")
        
        # Run initial health check
        self._is_healthy = await self.health_check()
        if not self._is_healthy:
            logger.warning("Ollama service health check failed at startup")
        else:
            logger.info("Ollama service is healthy")
            
        # Start periodic health check task if enabled
        if self.health_check_enabled:
            self._health_check_task = asyncio.create_task(self._periodic_health_check())
            logger.info(f"Started periodic health check (interval: {self.health_check_interval}s)")
            
    async def _cleanup(self):
        """Cleanup resources"""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
                
        if self._client:
            await self._client.aclose()
                
        self._client = None
        
    def _get_metrics(self, model: str) -> ModelMetrics:
        """Get or create metrics for a model"""
        if model not in self._metrics:
            self._metrics[model] = ModelMetrics()
        return self._metrics[model]
        
    def _is_circuit_open(self, model: str) -> bool:
        """Check if circuit breaker is open for a model"""
        metrics = self._get_metrics(model)
        
        if not metrics.circuit_open:
            return False
            
        # Check if cooldown period has passed
        if metrics.circuit_open_until and time.time() >= metrics.circuit_open_until:
            logger.info(f"Circuit breaker cooldown expired for {model}, resetting")
            metrics.circuit_open = False
            metrics.circuit_open_until = None
            metrics.consecutive_failures = 0
            return False
            
        return True
        
    def _record_success(self, model: str, latency: float):
        """Record successful request"""
        metrics = self._get_metrics(model)
        metrics.request_count += 1
        metrics.success_count += 1
        metrics.consecutive_failures = 0
        metrics.total_latency += latency
        metrics.last_success = time.time()
        
    def _record_failure(self, model: str):
        """Record failed request and check circuit breaker"""
        metrics = self._get_metrics(model)
        metrics.request_count += 1
        metrics.failure_count += 1
        metrics.consecutive_failures += 1
        metrics.last_failure = time.time()
        
        # Check if circuit breaker threshold reached
        if metrics.consecutive_failures >= self.circuit_breaker_threshold:
            metrics.circuit_open = True
            metrics.circuit_open_until = time.time() + self.circuit_breaker_timeout
            logger.error(
                f"Circuit breaker opened for {model} after {metrics.consecutive_failures} "
                f"consecutive failures. Will retry after {self.circuit_breaker_timeout}s"
            )
            
    async def health_check(self) -> bool:
        """
        Check if Ollama service is available.
        
        Returns:
            True if service is healthy, False otherwise
        """
        try:
            if not self._client:
                return False
                
            # Try to list models as health check
            await self._client.list()
            return True
            
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.debug(f"Ollama health check failed: {e}")
            return False
        except Exception as e:
            logger.warning(f"Unexpected error during health check: {e}")
            return False
            
    async def _periodic_health_check(self):
        """Run periodic health checks and validate required models"""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                
                # Check service health
                is_healthy = await self.health_check()
                
                if not is_healthy:
                    self._is_healthy = False
                    logger.error("Periodic health check failed: Ollama service unavailable")
                    continue
                
                # Validate required models
                all_models_available = True
                for model_name in self.required_models:
                    model_available = await self.check_model(model_name)
                    if not model_available:
                        all_models_available = False
                        logger.error(f"Required model '{model_name}' is not available")
                
                self._is_healthy = is_healthy and all_models_available
                
                if self._is_healthy:
                    logger.debug("Periodic health check passed")
                else:
                    logger.warning("Periodic health check failed: Required models missing")
                    
            except asyncio.CancelledError:
                logger.info("Periodic health check task cancelled")
                raise
            except Exception as e:
                logger.error(f"Error in periodic health check: {e}")
                self._is_healthy = False
            
    async def check_model(self, model_name: str) -> bool:
        """
        Check if a specific model is available.
        
        Args:
            model_name: Name of the model to check
            
        Returns:
            True if model is available, False otherwise
        """
        try:
            if not self._client:
                return False
                
            models = await self._client.list()
            available_models = [m['name'] for m in models.get('models', [])]
            
            if model_name in available_models:
                return True
            else:
                logger.warning(f"Model '{model_name}' not found. Available models: {available_models}")
                logger.info(f"To download model, run: ollama pull {model_name}")
                return False
                
        except Exception as e:
            logger.error(f"Error checking model availability: {e}")
            return False
            
    async def generate(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs
    ) -> Union[GenerateResponse, AsyncGenerator[str, None]]:
        """
        Generate text using specified model.
        
        Args:
            model: Model name
            prompt: Input prompt
            system: Optional system message
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            stream: Whether to stream response
            **kwargs: Additional Ollama parameters
            
        Returns:
            GenerateResponse or async generator of text chunks
            
        Raises:
            OllamaConnectionError: Cannot connect to service
            OllamaModelNotFoundError: Model not available
            OllamaGenerationError: Generation failed
        """
        if not self._client:
            raise OllamaConnectionError("Client not initialized")
            
        # Check circuit breaker
        if self._is_circuit_open(model):
            raise OllamaGenerationError(
                f"Circuit breaker is open for {model}. Service temporarily unavailable."
            )
            
        # Build options
        options = {
            "temperature": temperature,
        }
        if max_tokens:
            options["num_predict"] = max_tokens
        options.update(kwargs)
        
        # Build request payload
        request_data = {
            "model": model,
            "prompt": prompt,
            "options": options,
            "stream": stream,
        }
        if system:
            request_data["system"] = system
            
        start_time = time.time()
        
        try:
            logger.debug(f"Generating with model {model}, stream={stream}")
            
            if stream:
                return self._stream_generate(model, request_data, start_time)
            else:
                response = await self._generate_with_retry(model, request_data)
                latency = time.time() - start_time
                
                self._record_success(model, latency)
                
                return GenerateResponse(
                    text=response.get('response', ''),
                    model=response.get('model', model),
                    total_duration=response.get('total_duration'),
                    load_duration=response.get('load_duration'),
                    prompt_eval_count=response.get('prompt_eval_count'),
                    eval_count=response.get('eval_count'),
                )
                
        except Exception as e:
            self._record_failure(model)
            logger.error(f"Generation failed for model {model}: {e}")
            raise OllamaGenerationError(f"Generation failed: {e}") from e
            
    async def _generate_with_retry(self, model: str, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate with exponential backoff retry logic"""
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                response = await self._client.generate(**request_data)
                return response
                
            except httpx.ConnectError as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt) * (0.5 + 0.5 * time.time() % 1)
                    logger.warning(
                        f"Connection error on attempt {attempt + 1}/{self.max_retries}, "
                        f"retrying in {delay:.2f}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    raise OllamaConnectionError(f"Failed to connect after {self.max_retries} attempts") from e
                    
            except httpx.TimeoutException as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Timeout on attempt {attempt + 1}/{self.max_retries}, "
                        f"retrying in {delay:.2f}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    raise OllamaGenerationError(f"Request timed out after {self.max_retries} attempts") from e
                    
            except Exception as e:
                # Non-retryable error
                if "not found" in str(e).lower():
                    raise OllamaModelNotFoundError(f"Model '{model}' not found. Run: ollama pull {model}") from e
                else:
                    raise
                    
        raise OllamaGenerationError(f"Generation failed after {self.max_retries} attempts") from last_exception
        
    async def _stream_generate(
        self,
        model: str,
        request_data: Dict[str, Any],
        start_time: float
    ) -> AsyncGenerator[str, None]:
        """Stream generation with error handling"""
        try:
            stream = await self._client.generate(**request_data)
            
            async for chunk in stream:
                if 'response' in chunk:
                    yield chunk['response']
                    
            latency = time.time() - start_time
            self._record_success(model, latency)
            
        except Exception as e:
            self._record_failure(model)
            logger.error(f"Streaming generation failed for model {model}: {e}")
            raise OllamaGenerationError(f"Streaming failed: {e}") from e
            
    async def embed(
        self,
        model: str,
        input: Union[str, List[str]]
    ) -> EmbedResponse:
        """
        Generate embeddings for text input.
        
        Args:
            model: Embedding model name
            input: Text or list of texts to embed
            
        Returns:
            EmbedResponse with embeddings
            
        Raises:
            OllamaConnectionError: Cannot connect to service
            OllamaModelNotFoundError: Model not available
        """
        if not self._client:
            raise OllamaConnectionError("Client not initialized")
            
        # Check circuit breaker
        if self._is_circuit_open(model):
            raise OllamaGenerationError(
                f"Circuit breaker is open for {model}. Service temporarily unavailable."
            )
            
        start_time = time.time()
        
        try:
            # Convert single string to list for API
            input_list = [input] if isinstance(input, str) else input
            
            logger.debug(f"Generating embeddings with model {model} for {len(input_list)} inputs")
            
            response = await self._embed_with_retry(model, input_list)
            
            latency = time.time() - start_time
            self._record_success(model, latency)
            
            return EmbedResponse(
                embeddings=response.get('embeddings', []),
                model=model
            )
            
        except Exception as e:
            self._record_failure(model)
            logger.error(f"Embedding generation failed for model {model}: {e}")
            raise OllamaGenerationError(f"Embedding failed: {e}") from e
            
    async def _embed_with_retry(self, model: str, input_list: List[str]) -> Dict[str, Any]:
        """Embed with retry logic"""
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                response = await self._client.embed(model=model, input=input_list)
                return response
                
            except httpx.ConnectError as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt) * (0.5 + 0.5 * time.time() % 1)
                    logger.warning(
                        f"Connection error on attempt {attempt + 1}/{self.max_retries}, "
                        f"retrying in {delay:.2f}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    raise OllamaConnectionError(f"Failed to connect after {self.max_retries} attempts") from e
                    
            except httpx.TimeoutException as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Timeout on attempt {attempt + 1}/{self.max_retries}, "
                        f"retrying in {delay:.2f}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    raise OllamaGenerationError(f"Embedding request timed out after {self.max_retries} attempts") from e
                    
            except Exception as e:
                if "not found" in str(e).lower():
                    raise OllamaModelNotFoundError(f"Model '{model}' not found. Run: ollama pull {model}") from e
                else:
                    raise
                    
        raise OllamaGenerationError(f"Embedding failed after {self.max_retries} attempts") from last_exception
        
    async def generate_with_fallback(
        self,
        model: str,
        prompt: str,
        fallback_models: List[str],
        **kwargs
    ) -> GenerateResponse:
        """
        Generate with automatic fallback to alternative models.
        
        Args:
            model: Primary model name
            prompt: Input prompt
            fallback_models: List of fallback models to try
            **kwargs: Additional generate parameters
            
        Returns:
            GenerateResponse from whichever model succeeded
        """
        models_to_try = [model] + fallback_models
        last_exception = None
        
        for model_name in models_to_try:
            try:
                logger.info(f"Attempting generation with model: {model_name}")
                response = await self.generate(model=model_name, prompt=prompt, **kwargs)
                
                if model_name != model:
                    logger.warning(f"Primary model '{model}' failed, used fallback '{model_name}'")
                    
                return response
                
            except Exception as e:
                last_exception = e
                logger.warning(f"Model '{model_name}' failed: {e}")
                continue
                
        raise OllamaGenerationError(
            f"All models failed. Tried: {models_to_try}"
        ) from last_exception
        
    async def get_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata about a specific model.
        
        Args:
            model_name: Model name
            
        Returns:
            Model information dict or None if not found
        """
        try:
            if not self._client:
                return None
                
            models = await self._client.list()
            
            for model in models.get('models', []):
                if model['name'] == model_name:
                    return model
                    
            return None
            
        except Exception as e:
            logger.error(f"Error getting model info: {e}")
            return None
            
    async def list_models(self) -> List[str]:
        """
        List all available models.
        
        Returns:
            List of model names
        """
        try:
            if not self._client:
                return []
                
            models = await self._client.list()
            return [m['name'] for m in models.get('models', [])]
            
        except Exception as e:
            logger.error(f"Error listing models: {e}")
            return []
            
    async def pull_model(self, model_name: str) -> bool:
        """
        Download a model if not available.
        
        Args:
            model_name: Model name to pull
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self._client:
                return False
                
            logger.info(f"Pulling model: {model_name}")
            
            # Pull model (this may take a while)
            await self._client.pull(model_name)
            
            logger.info(f"Successfully pulled model: {model_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error pulling model: {e}")
            return False
            
    def get_metrics(self, model: Optional[str] = None) -> Dict[str, ModelMetrics]:
        """
        Get performance metrics.
        
        Args:
            model: Optional specific model name, or all if None
            
        Returns:
            Dict of model metrics
        """
        if model:
            return {model: self._get_metrics(model)}
        else:
            return self._metrics.copy()
