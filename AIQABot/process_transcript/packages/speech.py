import requests
from packages.models import Call
from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import cloud_speech

def queueTranscript(call: Call):
    client = SpeechClient()
    config = cloud_speech.RecognitionConfig(
            auto_decoding_config= cloud_speech.AutoDetectDecodingConfig(),
            language_codes= ['en-US'],
            model='telephony'
    )
    files = [
        cloud_speech.BatchRecognizeFileMetadata(uri=f'gs://aiqa_storage/calls/{call.uuid}/audio.mp3')

    ]

    request = cloud_speech.BatchRecognizeRequest(
        recognizer=f"projects/ai-qa-bot-412819/locations/global/recognizers/_",
        config=config,
        files=files,
        recognition_output_config=cloud_speech.RecognitionOutputConfig(
            gcs_output_config=cloud_speech.GcsOutputConfig(
                uri=f"gs://aiqa_storage/calls/{call.uuid}/transcript/",
            ),
        ),
        processing_strategy=cloud_speech.BatchRecognizeRequest.ProcessingStrategy.DYNAMIC_BATCHING,

    )

    
    client.batch_recognize(request=request)