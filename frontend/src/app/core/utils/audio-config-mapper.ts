import { ProjectConfig } from '../models/project-config.model';

export const mapAudioDtoToModel = (dto: any) => ({
    inputDeviceId: dto.input_device_id,
    sampleRate: dto.sample_rate,
    channels: dto.channels,
    chunkSize: dto.chunk_size,
    enableVad: dto.enable_vad,
    vadThreshold: dto.vad_threshold,
    silenceTimeout: dto.silence_timeout,
    minAudioLength: dto.min_audio_length,
    maxAudioLength: dto.max_audio_length,
    triggerWords: dto.trigger_words,
    ignoreTriggerWords: dto.ignore_trigger_words,
});

export const mapAudioModelToDto = (
    audio: ProjectConfig['audio'] | Partial<ProjectConfig['audio']>
) => {
    const dto: Record<string, any> = {};

    if (audio.inputDeviceId !== undefined) {
        dto.input_device_id = audio.inputDeviceId;
    }
    if (audio.sampleRate !== undefined) {
        dto.sample_rate = audio.sampleRate;
    }
    if (audio.channels !== undefined) {
        dto.channels = audio.channels;
    }
    if (audio.chunkSize !== undefined) {
        dto.chunk_size = audio.chunkSize;
    }
    if (audio.enableVad !== undefined) {
        dto.enable_vad = audio.enableVad;
    }
    if (audio.vadThreshold !== undefined) {
        dto.vad_threshold = audio.vadThreshold;
    }
    if (audio.silenceTimeout !== undefined) {
        dto.silence_timeout = audio.silenceTimeout;
    }
    if (audio.minAudioLength !== undefined) {
        dto.min_audio_length = audio.minAudioLength;
    }
    if (audio.maxAudioLength !== undefined) {
        dto.max_audio_length = audio.maxAudioLength;
    }
    if (audio.triggerWords !== undefined) {
        dto.trigger_words = audio.triggerWords;
    }
    if (audio.ignoreTriggerWords !== undefined) {
        dto.ignore_trigger_words = audio.ignoreTriggerWords;
    }

    return dto;
};
