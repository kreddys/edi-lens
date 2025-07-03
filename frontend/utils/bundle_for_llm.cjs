#!/usr/bin/env node

const fs = require('node:fs');
const path = require('node:path');

// --- Configuration ---
const projectRoot = process.cwd(); // Assumes script is run from the project root
const outputFileName = 'edi_lens_bundle.txt'; // Name of the output file
const srcDir = 'src'; // Main source directory to include
const includeDirs = [srcDir]; // Add other top-level dirs if needed (e.g., 'public')
const includeFiles = [
    'package.json',
    'vite.config.ts',
    'tailwind.config.ts', // Assuming you have this file
    'postcss.config.cjs', // Assuming you have this file
    'tsconfig.json',
    'tsconfig.app.json',
    'tsconfig.node.json',
    'index.html',
    '.gitignore', // Include .gitignore for context on excluded files
];
const includeExtensions = [
    '.ts',
    '.tsx',
    '.js',
    '.jsx',
    '.css',
    '.cjs', // Include cjs for config files
    '.mjs',
    '.json', // Still include JSON for package.json, tsconfig etc. but exclude src/schemas below
    '.html',
];
const excludeDirsInput = [ // Renamed to clarify input vs processed paths
    'node_modules',
    'dist',
    '.git',
    '.vscode',
    'coverage',
    'src/schemas', // Explicitly exclude schemas directory within src
    '.husky', // Common Git hooks directory
    'public/mockServiceWorker.js', // Example specific file exclusion
    'storybook-static', // Storybook build output
    '.github', // GitHub actions/workflows
    '.idea', // JetBrains IDE config
];
const excludeFiles = [
    'package-lock.json',
    outputFileName,
    '.env', // Exclude environment files
    '.env.*', // Exclude specific environment files like .env.local
    // Add specific files to exclude if needed
];
// --- End Configuration ---

// Normalize excludeDirs to absolute paths for reliable checking
const excludeDirs = excludeDirsInput.map(dir => path.join(projectRoot, dir));

const outputFilePath = path.join(projectRoot, outputFileName);
let bundledContent = '';
let fileCount = 0;

console.log(`Starting bundling process for project: ${projectRoot}`);
console.log(`Output will be saved to: ${outputFilePath}`);

// Function to recursively get all relevant files
function getAllFiles(dirPath, arrayOfFiles = []) {
    try {
        const files = fs.readdirSync(dirPath);

        files.forEach(function (file) {
            const currentPath = path.join(dirPath, file);
            const relativePath = path.relative(projectRoot, currentPath);

            // --- Improved Exclusion Check ---
            // Check if the current path starts with any excluded directory path
            const isExcludedDir = excludeDirs.some(excludedDir =>
                currentPath.startsWith(excludedDir + path.sep) || currentPath === excludedDir
            );
            if (isExcludedDir) {
                // console.log(`  Skipping excluded directory content: ${relativePath}`); // Optional: verbose logging
                return;
            }
            // Check if the file name itself is excluded
            if (excludeFiles.includes(file)) {
                // console.log(`  Skipping excluded file: ${relativePath}`); // Optional: verbose logging
                return;
            }
            // Check against wildcard file exclusions (like .env.*)
            const isExcludedFilePattern = excludeFiles.some(pattern => {
                if (pattern.includes('*')) {
                    const regex = new RegExp('^' + pattern.replace('.', '\\.').replace('*', '.*') + '$');
                    return regex.test(file);
                }
                return false;
            });
            if (isExcludedFilePattern) {
                // console.log(`  Skipping excluded file pattern: ${relativePath}`); // Optional: verbose logging
                return;
            }
            // -------------------------------

            try {
                if (fs.statSync(currentPath).isDirectory()) {
                    arrayOfFiles = getAllFiles(currentPath, arrayOfFiles); // Recurse
                } else {
                    // Check if the file extension is in the include list
                    if (includeExtensions.includes(path.extname(file).toLowerCase())) {
                        arrayOfFiles.push(currentPath);
                    } else {
                        // console.log(`  Skipping due to extension: ${relativePath}`); // Optional: verbose logging
                    }
                }
            } catch (statError) {
                console.warn(`  Warning: Could not stat ${relativePath}. Skipping. Error: ${statError.message}`);
            }
        });

        return arrayOfFiles;
    } catch (readDirError) {
        console.error(`  Error reading directory ${dirPath}. Skipping. Error: ${readDirError.message}`);
        return arrayOfFiles;
    }
}

// Process top-level included directories
const allFilesToProcess = [];
includeDirs.forEach(dir => {
    const dirFullPath = path.join(projectRoot, dir);
    if (fs.existsSync(dirFullPath)) {
        // Check if the top-level directory itself is excluded
        const isTopLevelExcludedDir = excludeDirs.some(excludedDir => dirFullPath === excludedDir);
        if (isTopLevelExcludedDir) {
            console.log(`Skipping excluded top-level directory: ${dir}`);
            return;
        }
        console.log(`Processing directory: ${dir}`);
        getAllFiles(dirFullPath, allFilesToProcess);
    } else {
        console.warn(`Include directory not found: ${dir}`);
    }
});

// Add top-level included files (checking exclusion patterns)
includeFiles.forEach(file => {
    const fileFullPath = path.join(projectRoot, file);

    // Check standard file exclusion
    if (excludeFiles.includes(file)) {
        console.log(`Skipping explicitly excluded file: ${file}`);
        return;
    }
    // Check wildcard file exclusion
    const isExcludedFilePattern = excludeFiles.some(pattern => {
        if (pattern.includes('*')) {
            const regex = new RegExp('^' + pattern.replace('.', '\\.').replace('*', '.*') + '$');
            return regex.test(file);
        }
        return false;
    });
    if (isExcludedFilePattern) {
        console.log(`Skipping excluded file pattern: ${file}`);
        return;
    }

    if (fs.existsSync(fileFullPath)) {
        try {
            if (fs.statSync(fileFullPath).isFile()) {
                // Check if the full path is within an excluded directory
                const isExcludedDir = excludeDirs.some(excludedDir =>
                    fileFullPath.startsWith(excludedDir + path.sep) || fileFullPath === excludedDir
                );
                if (!isExcludedDir && !allFilesToProcess.includes(fileFullPath)) {
                    allFilesToProcess.push(fileFullPath);
                } else if (isExcludedDir) {
                    console.log(`Skipping file within excluded directory: ${file}`);
                }
            } else {
                console.warn(`Include entry is a directory, skipping: ${file}`);
            }
        } catch (statError) {
            console.warn(`Warning: Could not stat included file ${file}. Skipping. Error: ${statError.message}`);
        }
    } else {
        console.warn(`Include file not found: ${file}`);
    }
});

console.log(`Found ${allFilesToProcess.length} files to bundle.`);

// Read each file and append its content to the bundle
allFilesToProcess.forEach(filePath => {
    try {
        const relativePath = path.relative(projectRoot, filePath);
        // Final check: ensure the relative path doesn't *start* with an excluded dir pattern again
        // This helps catch edge cases, though the main logic should handle it
        const isExcludedRelative = excludeDirsInput.some(excludedDirPrefix =>
            relativePath.startsWith(excludedDirPrefix + path.sep)
        );
        if (isExcludedRelative) {
            console.log(`  Skipping excluded relative path at final stage: ${relativePath}`);
            return;
        }


        console.log(`  Adding: ${relativePath}`);
        const fileContent = fs.readFileSync(filePath, 'utf8');

        bundledContent += `--- START OF FILE ${relativePath.replace(/\\/g, '/')} ---\n\n`; // Standardize path sep for header
        bundledContent += fileContent;
        bundledContent += `\n\n--- END OF FILE ${relativePath.replace(/\\/g, '/')} ---\n\n`;
        fileCount++;
    } catch (readFileError) {
        console.error(`  Error reading file ${filePath}. Skipping. Error: ${readFileError.message}`);
    }
});

// Write the bundled content to the output file
try {
    fs.writeFileSync(outputFilePath, bundledContent, 'utf8');
    console.log(`\nSuccessfully bundled ${fileCount} files into ${outputFileName}`);
} catch (writeFileError) {
    console.error(`\nError writing output file ${outputFilePath}. Error: ${writeFileError.message}`);
}