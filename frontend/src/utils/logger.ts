const DEBUG_FLAG = localStorage.getItem('debug');

const isDebugMode = (scope?: string): boolean => {
    if (!DEBUG_FLAG) return false;
    if (DEBUG_FLAG === 'true') return true;
    return scope ? DEBUG_FLAG.split(',').includes(scope) : false;
};

export const getLogger = (scope: string) => {
    const prefix = `[${scope}]`;
    return {
        log: (...args: any[]) => console.log(prefix, ...args),
        warn: (...args: any[]) => console.warn(prefix, ...args),
        error: (...args: any[]) => console.error(prefix, ...args),
        debug: (...args: any[]) => {
            if (isDebugMode(scope)) {
                console.log(`%c${prefix}`, 'color: blue;', ...args);
            }
        },
        // --- THIS IS THE FIX ---
        // Add the group methods to the logger utility.
        // We will only execute them if debug mode is enabled for the scope.
        groupCollapsed: (...args: any[]) => {
            if (isDebugMode(scope)) {
                console.groupCollapsed(`%c${prefix}`, 'color: blue;', ...args);
            }
        },
        groupEnd: () => {
            if (isDebugMode(scope)) {
                console.groupEnd();
            }
        },
        // --- END OF FIX ---
    };
};