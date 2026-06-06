import asyncio
import os

try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
except ImportError:
    torch = None
    AutoModelForCausalLM = None
    AutoTokenizer = None

class LocalLLMManager:
    def __init__(self, model_path: str, backend: str = "transformers"):
        self.model_path = model_path
        self.backend = backend.lower()
        self.model = None
        self.tokenizer = None
        self.device = "cpu"
        self._initialize_engine()

    def _initialize_engine(self) -> None:
        """
        Initialise le moteur LLM pour une exécution locale compatible Windows.
        """
        if torch is None or AutoModelForCausalLM is None or AutoTokenizer is None:
            raise RuntimeError(
                "Dépendances LLM manquantes. Installe requirements-full.txt pour activer le moteur local."
            )

        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        if self.backend == "vllm":
            raise RuntimeError(
                "vLLM n'est pas supporté sur Windows pour ce projet. Utilise LLM_BACKEND=transformers."
            )

        if self.backend != "transformers":
            raise RuntimeError(
                f"Backend LLM non supporté: {self.backend}. Utilise LLM_BACKEND=transformers."
            )

        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                f"Le modèle local est introuvable: {self.model_path}. Configure LLM_MODEL_PATH vers un dossier valide."
            )

        print(f"Chargement du modèle depuis {self.model_path} sur {self.device}...")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        
        dtype = torch.float16 if self.device == "cuda" else torch.float32

        # Chargement standard du modèle (Sans compression 4-bit)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            torch_dtype=dtype,
            device_map="cuda" if self.device == "cuda" else None,
        )
        if self.device == "cpu":
            self.model = self.model.to(self.device)

    async def generate_response(self, prompt: str, max_tokens: int = 512, temperature: float = 0.1) -> str:
        """
        Génère une réponse optimisée, rapide et sans hallucination.
        """
        if self.model is None or self.tokenizer is None:
            raise RuntimeError("Le moteur LLM n'a pas pu être initialisé.")

        def _generate() -> str:
            # 1. Formatage strict pour que Qwen comprenne son rôle
            messages = [
                {"role": "system", "content": "Tu es un assistant IA expert. Réponds de manière concise, directe et professionnelle. Ne rajoute jamais de formules de politesse ou de signatures."},
                {"role": "user", "content": prompt}
            ]
            
            # Application du template officiel du modèle
            formatted_prompt = self.tokenizer.apply_chat_template(
                messages, 
                tokenize=False, 
                add_generation_prompt=True
            )

            inputs = self.tokenizer(formatted_prompt, return_tensors="pt")
            input_ids = inputs["input_ids"]
            if self.device == "cuda":
                inputs = {key: value.to(self.device) for key, value in inputs.items()}

            # 2. Génération avec gestion stricte de l'arrêt
            generated_tokens = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                do_sample=True, # Activé pour la température
                temperature=temperature,
                repetition_penalty=1.15, # Empêche le modèle de radoter
                pad_token_id=self.tokenizer.eos_token_id,
                eos_token_id=self.tokenizer.eos_token_id # Force l'arrêt net à la fin de la phrase
            )
            
            new_tokens = generated_tokens[0][input_ids.shape[-1]:]
            return self.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

        return await asyncio.to_thread(_generate)