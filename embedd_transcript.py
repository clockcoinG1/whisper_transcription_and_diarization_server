import json
import pickle
import uuid
import numpy as np
import pandas as pd
import requests
import tiktoken
from openai.embeddings_utils import get_embedding,cosine_similarity
import openai


class Embedder:
		def __init__(self, embedding_model, input_datapath, embedding_encoding, max_tokens):
				self.EMBEDDING_MODEL = "text-embedding-ada-002"
				api_key =  "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"
				self.base = 'https://api.openai.com/v1/chat/completions'
				self.headers = {
						'Content-Type': 'application/json',
						'Authorization': 'Bearer ' + api_key,
				}

				self.MAX_SECTION_LEN = 1500
				self.SEPARATOR = "\n* "
				self.ENCODING = "gpt2"
				self.COMPLETIONS_MODEL = "text-davinci-003"
				self.embedding_model = embedding_model
				self.embedding_encoding = embedding_encoding
				self.max_tokens = max_tokens
				self.result_dict = None
				self.embedding_cache_path = 'cache/'
				self.df = pd.read_csv(input_datapath, delimiter="\t", engine='python', names=["start_time", "end_time", "speaker_number", "transcript"])

				print(
					f"DataFrame of size:{self.df.size} shape:{self.df.shape}"
				)

		def compute_doc_embeddings(self):
				"""
				Create an embedding for each row in the dataframe using the OpenAI Embeddings API.
				Pickle the embeddings in the cache directory
				Return a dictionary that maps between each embedding vector and the index of the row that it corresponds to.
				data = {
						idx: get_embedding(df.combined) for idx, r in df.iterrows()
				}
				"""
				df = self.df
				df["embedding"] = df.combined.apply(lambda x: get_embedding(x, engine=self.embedding_model))
				return df


		def get_embedding(self, text: str):
				model = self.EMBEDDING_MODEL
				result = openai.Embedding.create(
					model=model,
					input=text
				)
				return result["data"][0]["embedding"]


		def vector_similarity(self, x, y):
				"""
				Returns the similarity between two vectors.
				Because OpenAI Embeddings are normalized to length 1, the cosine similarity is the same as the dot product.
				"""
				# dot product of 2 vectors
				return np.dot(np.array(x), np.array(y))


		def search_transcript(self, transcript_segment, n=10, pprint=True):
				df = self.result_dict
				product_embedding = get_embedding(
						transcript_segment,
						engine="text-embedding-ada-002"
				)
				df["similarity"] = df.embedding.apply(lambda x: cosine_similarity(x, product_embedding))

				self.result = (
						df.sort_values("similarity", ascending=False)
						.head(n)
						.combined.str.replace("Speaker #: ", "")
						.str.replace("; Transcript:", ": ")
				)
				if pprint:
						for r in self.result:
								print(r[:200])
								print("result saved")
				return self.result


		def order_document_sections_by_query_similarity(self, query):
			"""
			Find the query embedding for the supplied query, and compare it against all of the pre-calculated document embeddings
			to find the most relevant sections.
			Return the list of document sections, sorted by relevance in descending order.
			"""

			# MULTIPLY THE TWO MATRIXES
			self.query_embedding = get_embedding(query)

			document_similarities = sorted([
					(self.vector_similarity(self.query_embedding, doc_embedding), doc_index) for doc_index, doc_embedding in self.result_dict.items() if doc_index == 'embedding'

			], reverse=True)

			return document_similarities

		def load_doc_embeddings(self):
				"""
				Try to load the embeddings from the cache directory.
				If successful, read the cache file and return a dictionary that maps between each embedding vector and the index of the row that it corresponds to.
				Otherwise, call the function above to compute the embeddings.
				param df : dataframe object
				return : dictionary , pair of length and dimensions of the embedding space
				"""
				try:
						result_dict = pickle.load(open(f"{self.embedding_cache_path}dict_embedding.p", "rb"))  # load/deseralize

				except FileNotFoundError:

						print('No embeddings file found. Computing embeddings...')
						result_dict = self.compute_doc_embeddings()
						with open(f"{self.embedding_cache_path}dict_embedding.p", "wb") as f:
								pickle.dump(result_dict, f)  # serialize/save

				else:
						print(f'Using {len(result_dict)} precomputed embeddings.')
						self.result_dict = result_dict
						return self.result_dict
				self.result_dict = result_dict
				return self.result_dict

		def create_output_csv(self, embedding_dict):
				print(embedding_dict[1])
				df = pd.DataFrame.from_dict(embedding_dict, orient="index")
				df.columns = ["combined", "embedding"]
				df.to_csv(f'cache/output-{str(uuid.uuid4())}.csv', index=False, sep=' ', encoding='utf-8')

		def do_doc2vec(self):
				df = self.df
				embedding_dict = {}
				df["transcript"] = df["transcript"].str.strip()
				pat = r"[\s+\"]"
				df["transcript"] = df["transcript"].str.replace(pat, ' ')
				df["speaker_number"] = df["speaker_number"].str.replace('[^0-9]', '')
				df["start_time"] = df["start_time"].str.replace('[^0-9]', '')
				df["end_time"] = df["end_time"].str.replace('[^0-9]', '')
				top_n = 1500
				df["combined"] = (
						"timestamp: [" + df.start_time + " -> " + df.end_time + "]" + "; Speaker #" + df.speaker_number.str.strip()+ " ; Content : " +  df.transcript.str.strip() + ";"
				)
				df.drop(["start_time","end_time"], axis=1, inplace=True)
				encoding = tiktoken.get_encoding(self.embedding_encoding)
				df["n_tokens"] = df.combined.apply(lambda x: len(encoding.encode(x)))
				df = df[df.n_tokens <= self.max_tokens].tail(top_n)
				df = self.load_doc_embeddings()
				df_embedding_dict = self.load_doc_embeddings().copy()
				embedding_dict = {}
				for i in range(len(df_embedding_dict)):
						embedding_dict.update({i: {}})
						# embedding_dict[i].update({"start_time": df_embedding_dict.iloc[i]["start_time"]})
						# embedding_dict[i].update({"end_time": df_embedding_dict.iloc[i]["end_time"]})
						# embedding_dict[i].update({"speaker_number": df_embedding_dict.iloc[i]["speaker_number"]})
						# embedding_dict[i].update({"transcript": df_embedding_dict.iloc[i]["transcript"]})
						embedding_dict[i].update({"combined": df_embedding_dict.iloc[i]["combined"]})
						embedding_dict[i].update({"embedding": df_embedding_dict.iloc[i]["embedding"]})
				print("Printing Embeddings Dictionary")
				# print(embedding_dict[1])
				self.embedding_dict = embedding_dict
				try:
						df_embedding_dict = pickle.load(open(f"{self.embedding_cache_path}dict_embedding.p", "rb"))
				except FileNotFoundError:
						print('No embeddings file found. Computing embeddings...')
						df_embedding_dict = self.load_doc_embeddings


		def construct_prompt(self, question: str) -> str:

				encoding = tiktoken.get_encoding(self.ENCODING)
				separator_len = len(encoding.encode(self.SEPARATOR))

				f"Context separator contains {separator_len} tokens"
				'Context separator contains 3 tokens'
				"""
				Fetch relevant
				"""
				most_relevant_document_sections = self.search_transcript(transcript_segment=question, n=50)
				chosen_sections = []
				chosen_sections_len = 0

				for _ in most_relevant_document_sections:
						# Add contexts until we run out
						chosen_sections_len +=  separator_len + len(_.split(' '))
						if chosen_sections_len > self.MAX_SECTION_LEN:
								break

						chosen_sections.append(self.SEPARATOR + _.split("];")[1])
						# chosen_sections_indexes.append(str(section_index))

				# Useful diagnostic information
				print(f"Selected {len(chosen_sections)} document sections:")


				# header = """Answer the question as truthfully as possible using the provided context of podcast transcript, Given the question and the context,as truthfuly as you can. If you do not know the answer say \"I don't now\" "\n\nContext:\n"""
				# return header + "".join(chosen_sections) + "\n\n Q: " + question + "\n A:"

				self.chosen_sections = '\n'.join(chosen_sections)
				return f'''#### Context ####\n\n{self.chosen_sections}\n\n{question}'''

						#### Question ####
						# "brand names, websites, logo, proprietary software / product names  You are provided the following segments of a video transcription. You are to replace and update all existing branding / names with the Whop. brand. When you are done  output \"\n[END OF TRANSCRIPT]\""
						# {question}
						#### Answer ####


		def answer_query_with_context(
				self,
				query: str,
				show_prompt: bool = True
		) -> str:
				COMPLETIONS_API_PARAMS = {
						# We use temperature of 0.0 because it gives the most predictable, factual answer.
						"temperature": 0.85,
						"max_tokens": 2400,
						"model": self.COMPLETIONS_MODEL,
				}
				prompt = self.construct_prompt(
						query,
				)

				if show_prompt:
						print(prompt)

				response = openai.Completion.create(
										prompt=prompt,
										**COMPLETIONS_API_PARAMS
								)
				self.presponse = response["choices"][0]["text"].strip(" \n")
				print("===\n", prompt)
				return response["choices"][0]["text"].strip(" \n")


		def chatbot(self, prompt="brand names, websites, logo, proprietary software / product names" , chat=f"Generate the updated transcript segments using the brand to replace any brand names, websites, logo, proprietary software / product names found in the transcript with the Whop brand", brand = "Whop"):
			# "Generate the updated transcript segments using Whop to replace any other brands"
			messages = []
			# speaker_combined = dict(zip(self.df["transcript"], self.df["speaker_number"]))
			# for x,y in brand_embeddings.items():
			# 		messages.append({"role": "assistant", "content": f"[Speaker #: {str(y)}] Content: {x}"})
			brand_embeddings = self.construct_prompt(question = prompt)# "brand names, websites, logo, proprietary software / product names"

			r = requests.post(
								self.base, headers=self.headers , stream=True,
								json={
										"model": "gpt-3.5-turbo",
										"messages": [
										{"role": "system", "content": f"You are given relevent context from an audio transcription. You are to replace and update all existing brand names, websites, logo, proprietary software / product names with the provided brand: {brand}." }, # Set the behavior of ---the bot here****
										{"role": "system", "content": f"{brand_embeddings}" }, # Set the behavior of ---the bot here****
										{ "role": "user", "content": chat }
										# *messages,
									],
										"temperature": 0.8,
										"top_p": 0.5,
										"n": 1,
										"stop": ["\n[END OF TRANSCRIPT]"],
										"stream": True,
										"max_tokens": 1096,
										"presence_penalty": 0,
										"frequency_penalty": 0,
										"user": ""
								}
						)

						# handle the request event stream format that yield data-only server-sent events as they become available, with the stream terminated by a data: [DONE]
			for line in r.iter_lines():
				message = ""
				if line:
						data = line
						if data == "[DONE]":
								break
						else:
							# output += str(data)
							# print(output)
							data = json.loads(data[5:])
							if data["object"] == "chat.completion.chunk":
										if data["choices"][0]["finish_reason"] == "stop":
																		break
										else:
																		if "content" in data["choices"][0]["delta"]:
																			message += data["choices"][0]["delta"]["content"]
																			print(data["choices"][0]["delta"]["content"], flush=True, end="")
																		else:
																			message += " "

if __name__ == "__main__":
	embedder = Embedder(
			embedding_model="text-embedding-ada-002",
			embedding_encoding="cl100k_base",
			max_tokens=8000,
			input_datapath="media/f5de2947-6199-4095-a289-862ea75f1f7e.fo.txt",
	)

	embedder.do_doc2vec()
	embedder.chatbot()
	embedder.chatbot(chat="Explain ", prompt="brand names and services ")
