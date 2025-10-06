export interface DebugLogsDto {
    session_id: string;
    logs: LogsDto[]
}

export interface LogsDto {
    details: {
        context: string;
        error: string;
    }
    event_type: string;
    meta?: {
        source: string;
        severity: string;
    }
    session_id: string;
    timestamp: string;
}
