import asyncio
import os
from threading import Thread

try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer
except ImportError:
    torch = None
    AutoModelForCausalLM = None
    AutoTokenizer = None
    TextIteratorStreamer = None

class LocalLLMManager:
    def __init__(self, model_path: str, backend: str = "transformers"):
        self.model_path = model_path
        self.backend = backend.lower()
        self.model = None
        self.tokenizer = None
        self.device = "cpu"
        self._initialize_engine()

    def _initialize_engine(self) -> None:
        if torch is None or AutoModelForCausalLM is None or AutoTokenizer is None:
            raise RuntimeError("Dépendances LLM manquantes.")

        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Le modèle local est introuvable: {self.model_path}")

        print(f"Chargement du modèle depuis {self.model_path} sur {self.device}...")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        
        dtype = torch.float16 if self.device == "cuda" else torch.float32

        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            torch_dtype=dtype,
            device_map="cuda" if self.device == "cuda" else None,
        )
        if self.device == "cpu":
            self.model = self.model.to(self.device)

    async def stream_response(self, messages: list[dict], max_tokens: int = 512, temperature: float = 0.1):
        """
        Génère une réponse mot par mot (Streaming).
        """
        if self.model is None or self.tokenizer is None:
            raise RuntimeError("Le moteur LLM n'est pas initialisé.")

        # 1. Préparation du prompt
        system_prompt = {"role": "system", "content": "Tu es un assistant IA expert. Réponds de manière concise et professionnelle. Ne rajoute jamais de formules de politesse."}
        full_messages = [system_prompt] + messages
        
        formatted_prompt = self.tokenizer.apply_chat_template(
            full_messages, tokenize=False, add_generation_prompt=True
        )

        inputs = self.tokenizer(formatted_prompt, return_tensors="pt")
        if self.device == "cuda":
            inputs = {key: value.to(self.device) for key, value in inputs.items()}

        # 2. Configuration du Streamer (Le diffuseur de mots)
        streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
        
        generation_kwargs = dict(
            **inputs,
            streamer=streamer,
            max_new_tokens=max_tokens,
            do_sample=True,
            temperature=temperature
            # La ligne repetition_penalty a été supprimée ici !
            
        )

        # 3. Lancement de la génération dans un thread séparé
        thread = Thread(target=self.model.generate, kwargs=generation_kwargs)
        thread.start()

        # 4. On renvoie les mots au fur et à mesure
        for new_text in streamer:
            yield new_text
            await asyncio.sleep(0.01) # Permet à FastAPI de respirer