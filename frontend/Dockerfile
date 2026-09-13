# --- 1. asama: derleme -------------------------------------------------------
FROM node:24-bookworm-slim AS derleyici

WORKDIR /uygulama

# Once lockfile: bagimlilik degismedigi surece bu katman yeniden calismaz.
# `npm ci` lockfile'i BIREBIR uygular; `npm install` gibi surum yukseltmez.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# --- 2. asama: servis --------------------------------------------------------
FROM nginx:1.29-alpine

# Vite dev sunucusu BURADA KULLANILMAZ: o bir gelistirme aracidir, kaynak
# dosyalari donusturerek servis eder ve uretim icin tasarlanmamistir. Burada
# derlenmis statik dosyalar nginx'ten gelir.
COPY --from=derleyici /uygulama/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
