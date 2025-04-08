import logging
import time
import random
import os
import asyncio
import json
from typing import List, Dict, Any, Optional
from pathlib import Path

from google import genai
from google.genai import types

class AIDocumentGeneratorService:
    """Service for generating AI-based document summaries using Gemini"""

    def __init__(
        self,
        api_key: str,
        model_name: str = 'models/gemini-2.0-flash-lite'
    ):
        self.api_key = api_key
        self.model_name = model_name
        self.logger = logging.getLogger(__name__)

        # Initialize the Gemini client
        self.client = genai.Client(api_key=api_key)

    def _build_system_prompt_with_chunks(self, chunks: List[Dict[str, Any]]) -> str:
        """
        Build a system prompt that includes relevant document chunks with their metadata

        Args:
            chunks: List of dictionaries with chunk text and metadata

        Returns:
            System prompt with embedded chunk content
        """
        system_prompt = "Eres un asistente experto en licitaciones públicas españolas que SIEMPRE referencia sus fuentes. Aquí están los fragmentos relevantes de los documentos:\n\n"

        for i, chunk in enumerate(chunks):
            # Extract metadata from chunk
            pdf_path = chunk["metadata"]["pdf_path"]
            filename = os.path.basename(pdf_path) if pdf_path else "unknown"
            page = chunk["metadata"]["page_number"] if chunk["metadata"]["page_number"] else "unknown"
            chunk_id = chunk["metadata"]["chunk_id"]
            title = chunk["metadata"]["title"]

            # Include the chunk content with its metadata
            system_prompt += f"--- FRAGMENTO {i+1} ---\n"
            system_prompt += f"ID: {chunk_id}\n"
            system_prompt += f"Título: {title}\n"
            system_prompt += f"Documento: {filename}\n"
            system_prompt += f"Página: {page}\n"
            system_prompt += f"Contenido:\n{chunk['text']}\n\n"

        system_prompt += "INSTRUCCIONES IMPORTANTES:\n"
        system_prompt += "1. Analiza estos fragmentos y proporciona información precisa basándote en ellos.\n"
        system_prompt += "2. Cuando cites información de un fragmento, DEBES incluir su ID exacto entre corchetes [chunk_id: XXX] al final de cada afirmación importante.\n"
        system_prompt += "3. COPIA EXACTAMENTE los IDs de los fragmentos tal como aparecen. No abrevies ni cambies el formato.\n"
        system_prompt += "4. Los IDs tienen el formato chunk_documento,página,sección (por ejemplo: chunk_DOC20241111094338ANEXO_I,1,s2_3) - cópialos completos.\n"
        system_prompt += "5. No inventes información que no esté en los fragmentos proporcionados.\n"
        system_prompt += "6. Tu respuesta será mostrada al usuario con enlaces a las fuentes originales, por lo que es crucial que cites correctamente los IDs de fragmentos.\n"
        system_prompt += "7. IMPORTANTE: Los usuarios solo verán la información de un fragmento cuando utilizas la referencia EXACTA. Si modificas el ID, no podrán ver la información original.\n"
        system_prompt += "8. Estructura tu respuesta en formato markdown."

        return system_prompt

    def _load_chunks_from_json_string(self, chunks_json: str) -> List[Dict[str, Any]]:
        """
        Load chunks from a JSON string

        Args:
            chunks_json: JSON string containing chunks data

        Returns:
            List of dictionaries with chunk text and metadata
        """
        try:
            chunks = json.loads(chunks_json)
            return chunks
        except Exception as e:
            self.logger.error(f"Error loading chunks from JSON string: {e}")
            return []

    async def generate_ai_documents_with_content(
        self,
        chunks_json: str,
        questions: List[str],
        max_retries: int = 5
    ) -> Optional[str]:
        """
        Generate client-specific AI documents using markdown content directly

        Args:
            markdown_contents: List of markdown content strings
            chunks_json: JSON string containing chunks data
            questions: List of questions/sections to process
            max_retries: Maximum number of retries for API calls

        Returns:
            Generated AI document content if successful, None otherwise
        """
        self.logger.info("Generating AI documents from content in parallel...")

        # Load chunks from JSON string
        chunks = self._load_chunks_from_json_string(chunks_json)
        if not chunks:
            self.logger.error("No chunks could be loaded from JSON string")
            return None

        # Create system prompts
        chunks_system_prompt = self._build_system_prompt_with_chunks(chunks)

        # Create tasks for processing each section in parallel
        section_tasks = []
        for i, question in enumerate(questions):
            section_number = i + 1
            prompt = f"""Por favor, busca en los documentos proporcionados y completa de manera
            específica y detallada la siguiente plantilla.

            Plantilla: {question}

            IMPORTANTE: Responde siempre con la información extraida del texto, asume que el usuario
            final no tiene acceso al documento y debemos darle toda la información necesaria en nuestra
            respuesta. Cita textualmente el texto cuando sea relevante.
            Nunca respondas con "se especifica en el apartado...", siempre responde con la información final.
            Utiliza el formato markdown para tu respuesta.
            """

            # Use the chunks-based system prompt for better traceability
            task = self._process_section_with_retries(
                prompt, chunks_system_prompt, section_number,
                len(questions), time.time(), max_retries
            )
            section_tasks.append(task)

        # Wait for all sections to complete
        section_responses = await asyncio.gather(*section_tasks)

        # Combine all responses into a single document
        combined_response = ""
        for i, response in enumerate(section_responses):
            if response:
                combined_response += response + "\n\n"
            else:
                self.logger.warning(f"Section {i+1} did not generate a response")

        if not combined_response:
            self.logger.error("Failed to generate any content")
            return None

        return combined_response

    async def _process_section_with_retries(
        self, prompt, system_prompt, section_number,
        total_sections, section_start_time, max_retries
    ) -> Optional[str]:
        """Process a single section with retry logic"""
        retry_count = 0
        initial_delay = 1.0
        delay = initial_delay

        # Define generation config using the proper types.GenerateContentConfig
        generate_content_config = types.GenerateContentConfig(
            temperature=0.1,
            top_p=0.95,
            top_k=40,
            max_output_tokens=8192,
            response_mime_type="text/plain",
        )

        while retry_count <= max_retries:
            try:
                self.logger.info(f"Processing section {section_number}/{total_sections}...")

                # Use loop.run_in_executor to run the synchronous method in a thread pool
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.client.models.generate_content(
                        model=self.model_name,
                        contents=[
                            {
                                "role": "user",
                                "parts": [{"text": system_prompt}]
                            },
                            {
                                "role": "user",
                                "parts": [{"text": prompt}]
                            }
                        ],
                        config=generate_content_config
                    )
                )

                # Log token usage if available
                if hasattr(response, 'usage_metadata'):
                    section_time = time.time() - section_start_time
                    self.logger.info(f"\nSection {section_number} completed in {section_time:.2f} seconds")
                    self.logger.info(f"Token Usage:")
                    self.logger.info(f"  Prompt tokens: {response.usage_metadata.prompt_token_count}")
                    self.logger.info(f"  Response tokens: {response.usage_metadata.candidates_token_count}")
                    self.logger.info(f"  Section total: {response.usage_metadata.total_token_count}")

                self.logger.debug(f"AI GENERATED RESPONSE FOR SECTION {section_number}: {response.text[:100]}...")
                return response.text

            except Exception as e:
                retry_count += 1
                self.logger.error(f"Error processing section {section_number} (attempt {retry_count}/{max_retries}): {e}")

                if retry_count > max_retries:
                    self.logger.error(f"Failed to process section {section_number} after {max_retries} retries")
                    return None

                # Add jitter to avoid thundering herd
                jitter = random.uniform(0.8, 1.2)
                actual_delay = delay * jitter
                self.logger.info(f"Retrying in {actual_delay:.2f} seconds...")
                await asyncio.sleep(actual_delay)  # Use asyncio.sleep instead of time.sleep

                # Exponential backoff
                delay *= 2

        return None

    async def generate_conversational_summary(
        self,
        document_content: str,
        tender_id: str = None,
        max_retries: int = 3
    ) -> Optional[str]:
        """
        Generate a conversational summary based on the AI document

        Args:
            document_content: Content of the AI document
            tender_id: ID of the tender
            max_retries: Maximum number of retries for API calls

        Returns:
            Conversational summary if successful, None otherwise
        """
        self.logger.info("Generating conversational summary from AI document...")

        # Define generation config using the proper types.GenerateContentConfig
        generate_content_config = types.GenerateContentConfig(
            temperature=1,
            top_p=0.95,
            top_k=40,
            max_output_tokens=1200,
            response_mime_type="text/plain",
        )

        prompt = f"""
        Eres un asistente experto en licitaciones públicas. A continuación, te presento un documento detallado
        sobre la licitación.

        {document_content}

        Por favor, genera un resumen breve (máximo 1500 caracteres) en un estilo profesional y
        directo que destaque los puntos más importantes de esta licitación. Incluye el objeto, presupuesto,
        plazos clave y cualquier particularidad que consideres relevante.

        Ejemplo: La licitación 10/2024/CONM-CEE busca un proveedor para el suministro de plantas y decoración
        floral navideña en el centro de Jaén. El proyecto se divide en dos lotes: Suministro de plantas (7.040€ + IVA)
        y servicio de decoración (4.840€ + IVA), con un presupuesto total de 11.880€ + IVA. No se exige solvencia
        económica o técnica y el plazo de presentación de ofertas finaliza el 25/11/2024 a las 14:00. La adjudicación
        se realiza a la oferta económica más baja.  El contrato se extiende hasta fin de 2024 y el adjudicatario debe
        presentar una declaración responsable sobre medidas de igualdad de género en el mercado laboral.  Se deben
        cumplir las normas de protección medioambiental y la normativa vigente en materia laboral.  Los licitadores deben
        revisar los anexos para detalles específicos sobre las plantas, materiales y plazos de entrega.
        """

        # Retry with exponential backoff
        retry_count = 0
        initial_delay = 1.0
        delay = initial_delay

        while retry_count <= max_retries:
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=[{
                        "role": "user",
                        "parts": [{"text": prompt}]
                    }],
                    config=generate_content_config
                )

                # Log token usage if available
                if hasattr(response, 'usage_metadata'):
                    self.logger.info("\nToken Usage (Summary):")
                    self.logger.info(f"Prompt tokens: {response.usage_metadata.prompt_token_count}")
                    self.logger.info(f"Response tokens: {response.usage_metadata.candidates_token_count}")
                    self.logger.info(f"Total tokens: {response.usage_metadata.total_token_count}")

                return response.text

            except Exception as e:
                retry_count += 1
                self.logger.error(f"Error generating conversational summary (attempt {retry_count}/{max_retries}): {e}")

                if retry_count > max_retries:
                    self.logger.error(f"Failed to generate conversational summary after {max_retries} retries")
                    return None

                # Add jitter to avoid thundering herd
                jitter = random.uniform(0.8, 1.2)
                actual_delay = delay * jitter
                self.logger.info(f"Retrying in {actual_delay:.2f} seconds...")
                time.sleep(actual_delay)

                # Exponential backoff
                delay *= 2

        return None
