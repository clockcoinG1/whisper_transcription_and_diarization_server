import csv
import math
import os

from diart import OnlineSpeakerDiarization
from diart.inference import RealTimeInference, RTTMWriter
from diart.sinks import RTTMWriter
from diart.sources import FileAudioSource


class StandardizeOutput:
		"""
		This class is used to standardize the output of the diarization system.
		It takes the whisper transcript csv file and wav file as input and outputs the
		standardized output rttm file and standard output.
		"""

		def __init__(self, csv_file_path, wav_file_path):
				self.rttm_map = []
				self.rttm_file_path = f"{wav_file_path.split('.')[0]}.rttm"
				self.final_output = f"{wav_file_path.split('.')[0]}.fo.txt"
				self.csv_file_path = csv_file_path
				self.wav_file_path = wav_file_path
				self.speaker_map = {}
				self.completed_diarization = []
				self.completed_diarization = []
				if not os.path.exists(self.rttm_file_path):
						self.pipeline = OnlineSpeakerDiarization()
						self.file = FileAudioSource(wav_file_path, 16000)
						self.inference = RealTimeInference(self.pipeline, self.file, do_plot=False)
						self.inference.attach_observers(RTTMWriter(self.file.uri, self.rttm_file_path))
						self.prediction = self.inference()
				else:
						print(f"{self.rttm_file_path} already exists, skipping diarization")

		def get_standardized_output(self):
				"""
				This method returns the standardized output of the diarization system.
				"""
				with open(self.rttm_file_path) as f:
						rttm_lines = f.readlines()
						for rttm_line in rttm_lines:
								parts = rttm_line.strip().split()
								self.speaker_map[float(parts[3]), float(parts[4])] = parts[7]

				for time_range, name in self.speaker_map.items():
						st_rttm = math.ceil(time_range[0] * 1000)
						et_rttm = math.ceil(time_range[1] * 1000 + st_rttm)
						self.rttm_map.append([st_rttm, et_rttm, name])

				with open(self.final_output, 'a+') as final_doc:
						with open(self.csv_file_path) as f:
								reader = csv.reader(f, quoting=csv.QUOTE_NONE)
								for z in reader:
										st_csv = int(z[0])
										min_diff = float('inf')
										speaker_name = None
										for rttm_entry in self.rttm_map:
												st_rttm = rttm_entry[0]
												diff = abs(st_csv - st_rttm)
												if diff < min_diff:
														min_diff = diff
														speaker_name = rttm_entry[2]
										self.completed_diarization.append([z[0], z[0], speaker_name, ' , '.join(z[2:])])
										final_doc.write(f"{z[0]},\t{z[1]},\t{speaker_name},\t{' , '.join(z[2:])}\n")
										print(f"{z[0]},\t{z[1]},\t{speaker_name},\t{' , '.join(z[2:])}\n")
										# final_doc.write(f"[{z[0]} - {z[0]}]\t{speaker_name}\t{' , '.join(z[2:])}\n")
				# print(self.completed_diarization)
				return f"File {self.final_output}"


"""
# DEBUG:
new_SO = StandardizeOutput(
		csv_file_path="media/dabc1da8-64a8-4626-bf87-9c6d0ad5d0d8.csv",
		wav_file_path="media/dabc1da8-64a8-4626-bf87-9c6d0ad5d0d8.wav",
)

new_SO.get_standardized_output()
"""
