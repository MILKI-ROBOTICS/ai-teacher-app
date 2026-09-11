import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.aiteacher.intelligence',
  appName: 'AI Teacher Intelligence',
  webDir: 'web',
  android: { allowMixedContent: false },
  server: { cleartext: false },
  plugins: {
    SplashScreen: { launchShowDuration: 0 },
    Camera: { presentationStyle: 'fullscreen' }
  }
};

export default config;
