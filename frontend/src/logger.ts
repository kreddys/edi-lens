export type AppLogLevel = 'log' | 'warn' | 'error' | 'debug' | 'info';

export type AppLogger = (message: string, level?: AppLogLevel) => void;

export const noOpLogger: AppLogger = () => { };

export const createLogger = (prefix: string): AppLogger => {
    return (message, level = 'log') => {
        const formatted = `[${prefix}] ${message}`;
        switch (level) {
            case 'warn': console.warn(formatted); break;
            case 'error': console.error(formatted); break;
            case 'info': console.info(formatted); break;
            case 'debug': console.debug(formatted); break;
            default: console.log(formatted); break;
        }
    };
};