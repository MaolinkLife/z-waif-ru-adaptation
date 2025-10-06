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

export const mapAudioModelToDto = (audio: ProjectConfig['audio']) => ({
    input_device_id: audio.inputDeviceId,
    sample_rate: audio.sampleRate,
    channels: audio.channels,
    chunk_size: audio.chunkSize,
    enable_vad: audio.enableVad,
    vad_threshold: audio.vadThreshold,
    silence_timeout: audio.silenceTimeout,
    min_audio_length: audio.minAudioLength,
    max_audio_length: audio.maxAudioLength,
    trigger_words: audio.triggerWords,
    ignore_trigger_words: audio.ignoreTriggerWords,
});
