/**
 * The path the API is mounted under while Vite serves the workbench.
 *
 * It is a module of its own because **two** things need it and they are
 * loaded in two different worlds: the application bundle, and the
 * development server's configuration. The configuration is bundled outside
 * the app's pipeline, so a module that read `import.meta.env` would fail
 * there — `import.meta.env` is the bundler's word, and the bundler is not
 * what loads the configuration.
 *
 * One constant for both is the point. A proxy mounted somewhere the
 * application does not ask for is a proxy that answers 404, and an
 * application asking somewhere the proxy is not is a request that never
 * leaves the machine.
 */
export const DEV_API_BASE = '/api'
