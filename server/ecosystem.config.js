module.exports = {
  apps: [
    {
      name: "hook-ai-server",
      script: "./server.js",
      instances: "max", // Spawns workers matching CPU core count
      exec_mode: "cluster", // Enables clustered load balancing
      watch: false, // Turn off watch in production to avoid restart loops
      max_memory_restart: "1G", // Restarts process if memory exceeds 1GB
      env: {
        NODE_ENV: "production",
        PORT: 3000
      }
    }
  ]
};
