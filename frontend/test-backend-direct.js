#!/usr/bin/env node

// Direct backend connectivity test outside of Jest

import http from 'http';

async function testBackendHealth() {
  return new Promise((resolve, reject) => {
    const req = http.request({
      hostname: 'localhost',
      port: 3001,
      path: '/api/v1/health',
      method: 'GET',
      timeout: 5000
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        console.log(`✅ Health check status: ${res.statusCode}`);
        console.log(`✅ Response data: ${data}`);
        resolve({ status: res.statusCode, data });
      });
    });

    req.on('error', (error) => {
      console.log(`❌ Health check failed: ${error.message}`);
      reject(error);
    });

    req.on('timeout', () => {
      console.log('❌ Health check timeout');
      req.destroy();
      reject(new Error('Timeout'));
    });

    req.end();
  });
}

async function testWithFetch() {
  try {
    const response = await fetch('http://localhost:3001/api/v1/health');
    console.log(`✅ Fetch health status: ${response.status}`);
    const data = await response.text();
    console.log(`✅ Fetch response data: ${data}`);
  } catch (error) {
    console.log(`❌ Fetch failed: ${error.message}`);
  }
}

async function main() {
  console.log('🔍 Testing backend connectivity...');
  
  console.log('\n1. Testing with http module:');
  try {
    await testBackendHealth();
  } catch (error) {
    console.log('HTTP module test failed');
  }

  console.log('\n2. Testing with fetch:');
  try {
    await testWithFetch();
  } catch (error) {
    console.log('Fetch test failed');
  }

  console.log('\n3. Testing backend services status:');
  console.log('Run: docker ps --filter "name=backend" --filter "name=frontend" --filter "name=caddy"');
}

main().catch(console.error);