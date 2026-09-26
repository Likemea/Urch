module.exports = {
  apps: [
    {
      name: 'Urch',
      script: 'main.py',
      interpreter: '/home/Dani/venv/bin/python3',
      max_memory_restart: '300M',
      cron_restart: '0 4 * * *',
      restart_delay: 5000,
      env_file: '/home/Dani/Urch/.env',
      env: {
        PYTHONUNBUFFERED: "1"
      }
    }
  ]
};