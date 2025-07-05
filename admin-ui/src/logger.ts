// A simple, controllable logger for the frontend.

// Check localStorage for a 'debug' flag. Can be 'true' or a comma-separated list of scopes.
const DEBUG_FLAG = localStorage.getItem('debug');

const isDebugMode = (scope?: string): boolean => {
    if (!DEBUG_FLAG) {
        return false;
    }
    if (DEBUG_FLAG === 'true') {
        return true;
    }
    // If a scope is provided, check if it's in the comma-separated list
    return scope ? DEBUG_FLAG.split(',').includes(scope) : false;
};

const getLogger = (scope: string) => {
    const prefix = `[${scope}]`;

    return {
        log: (...args: any[]) => console.log(prefix, ...args),
        warn: (...args: any[]) => console.warn(prefix, ...args),
        error: (...args: any[]) => console.error(prefix, ...args),
        // Debug logs only appear if debug mode is enabled for this scope (or globally)
        debug: (...args: any[]) => {
            if (isDebugMode(scope)) {
                console.log(`%c${prefix}`, 'color: blue;', ...args);
            }
        },
    };
};

export default getLogger;