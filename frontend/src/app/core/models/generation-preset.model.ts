export interface GenerationPreset {
    name: string;
    description: string;
    temperature: number;
    min_p: number;
    top_p: number;
    top_k: number;
    repeat_penalty: number;
    stop: string[] | null;
    num_predict: number;
}
