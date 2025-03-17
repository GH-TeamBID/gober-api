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

    def _build_system_prompt_with_documents(self, document_contents: List[Dict[str, str]]) -> str:
        """
        Build a system prompt that includes relevant document content

        Args:
            document_contents: List of dictionaries with document path and content

        Returns:
            System prompt with embedded document content
        """
        system_prompt = "Eres un asistente experto en licitaciones públicas españolas. Aquí están los documentos relevantes:\n\n"

        for i, doc in enumerate(document_contents):
            # Extract filename from path for better context
            filename = os.path.basename(doc["path"])

            # Include the full document content without truncation
            system_prompt += f"--- DOCUMENTO {i+1}: {filename} ---\n{doc['content']}\n\n"

        system_prompt += "Analiza estos documentos y proporciona información precisa basándote en ellos."
        return system_prompt

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

    def _prepare_document_contents(self, markdown_paths: List[str]) -> List[Dict[str, str]]:
        """
        Read the content of markdown files

        Args:
            markdown_paths: List of paths to markdown files

        Returns:
            List of dictionaries with document path and content
        """
        document_contents = []

        for file_path in markdown_paths:
            try:
                # Read the file content
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                document_contents.append({
                    "path": file_path,
                    "content": content
                })

                self.logger.debug(f"Successfully read content from {file_path}")

            except Exception as e:
                self.logger.error(f"Error reading markdown file {file_path}: {e}")

        return document_contents

    def _load_chunks_from_json(self, chunks_path: str) -> List[Dict[str, Any]]:
        """
        Load chunks from a JSON file

        Args:
            chunks_path: Path to the JSON file with chunks

        Returns:
            List of dictionaries with chunk text and metadata
        """
        try:
            with open(chunks_path, 'r', encoding='utf-8') as f:
                chunks = json.load(f)
            return chunks
        except Exception as e:
            self.logger.error(f"Error loading chunks from {chunks_path}: {e}")
            return []

    async def generate_ai_documents(
        self,
        markdown_paths: List[str],
        questions: List[str],
        output_file: str,
        max_retries: int = 5
    ) -> Optional[str]:
        """
        Generate client-specific AI documents by processing questions in parallel

        Args:
            markdown_paths: List of paths to markdown files
            questions: List of questions/sections to process
            output_file: File to write the results to
            max_retries: Maximum number of retries for API calls

        Returns:
            Path to the generated document if successful, None otherwise
        """
        self.logger.info("Generating AI documents in parallel...")

        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(output_file)
        os.makedirs(output_dir, exist_ok=True)

        # Create a directory for individual section responses
        sections_dir = os.path.join(output_dir, "sections")
        os.makedirs(sections_dir, exist_ok=True)

        # Read document contents directly (no caching)
        document_contents = self._prepare_document_contents(markdown_paths)

        if not document_contents:
            self.logger.error("No document contents could be loaded")
            return None

        # Build system prompt with all documents
        system_prompt = self._build_system_prompt_with_documents(document_contents)

        # Create tasks for processing each section in parallel
        tasks = []
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

            task = self._process_section_with_retries(
                prompt, system_prompt, section_number,
                len(questions), time.time(), max_retries
            )
            tasks.append(task)

        # Wait for all sections to complete
        section_responses = await asyncio.gather(*tasks)

        # Process results and save sections
        full_response = ""
        section_files = []

        for i, section_response in enumerate(section_responses):
            section_number = i + 1

            if not section_response:
                self.logger.error(f"Failed to generate section {section_number}")
                continue

            # Save this section to a separate file for logging
            section_file = os.path.join(sections_dir, f"section_{section_number}.md")
            with open(section_file, 'w', encoding='utf-8') as f:
                f.write(section_response)
            section_files.append(section_file)

            self.logger.info(f"Section {section_number} saved to {section_file}")
            full_response += section_response + "\n\n"

        # Only write the final document if we have content
        if full_response:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(full_response)
            self.logger.info(f"Complete AI document written to {output_file}")
            return output_file

        return None

    async def generate_ai_documents_with_chunks(
        self,
        markdown_paths: List[str],
        chunks_path: str,
        questions: List[str],
        output_file: str,
        max_retries: int = 5
    ) -> Optional[str]:
        """
        Generate client-specific AI documents using hierarchical chunks and processing questions in parallel

        Args:
            markdown_paths: List of paths to markdown files (for fallback)
            chunks_path: Path to the JSON file with chunks
            questions: List of questions/sections to process
            output_file: File to write the results to
            max_retries: Maximum number of retries for API calls

        Returns:
            Path to the generated document if successful, None otherwise
        """
        self.logger.info("Generating AI documents using chunks...")

        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(output_file)
        os.makedirs(output_dir, exist_ok=True)

        # Create a directory for individual section responses
        sections_dir = os.path.join(output_dir, "sections")
        os.makedirs(sections_dir, exist_ok=True)

        # Load chunks from JSON
        chunks = self._load_chunks_from_json(chunks_path)

        if not chunks:
            self.logger.warning("No chunks found, falling back to full document processing")
            return await self.generate_ai_documents(markdown_paths, questions, output_file, max_retries)

        # Build system prompt with chunks
        system_prompt = self._build_system_prompt_with_chunks(chunks)

        # Create tasks for processing each section in parallel
        tasks = []
        for i, question in enumerate(questions):
            section_number = i + 1
            prompt = f"""Por favor, busca en los fragmentos de documentos proporcionados y completa de manera
            específica y detallada la siguiente plantilla.

            Plantilla: {question}

            IMPORTANTE:
            1. Responde siempre con la información extraída del texto.
            2. Asume que el usuario final no tiene acceso al documento y debemos darle toda la información necesaria.
            3. Cita textualmente el texto cuando sea relevante.
            4. DEBES incluir el ID del fragmento [chunk_id: __________] después de cada sección importante que extraigas.
                ejemplo: [chunk_id: chunk_0_2_anexo_i]
                NO referencies más de un chunk en una misma lista.
                NO inventes chunks ID que no estén en la lista de chunks.
                Tus chunks serán procesados por una función regex que extraerá el ID del chunk re.compile(r'\\[chunk_id:\\s*([^\\]]+)\\]')
                y mapeará a un JSON por el chunk ID.
            """

            task = self._process_section_with_retries(
                prompt, system_prompt, section_number,
                len(questions), time.time(), max_retries
            )
            tasks.append(task)

        # Wait for all sections to complete
        section_responses = await asyncio.gather(*tasks)

        # Process results and save sections
        full_response = ""
        section_files = []

        for i, section_response in enumerate(section_responses):
            section_number = i + 1

            if not section_response:
                self.logger.error(f"Failed to generate section {section_number}")
                continue

            # Save this section to a separate file for logging
            section_file = os.path.join(sections_dir, f"section_{section_number}.md")
            with open(section_file, 'w', encoding='utf-8') as f:
                f.write(section_response)
            section_files.append(section_file)

            self.logger.info(f"Section {section_number} saved to {section_file}")
            full_response += section_response + "\n\n"

        # Only write the final document if we have content
        if full_response:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(full_response)
            self.logger.info(f"Complete AI document with chunk references written to {output_file}")
            return output_file

        return None

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
        tender_id: str,
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
        sobre la licitación {tender_id}.

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
