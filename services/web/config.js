// config.js
//
// Este arquivo é o ÚNICO ponto de acoplamento entre o serviço web e o
// serviço de API: uma URL configurável, não código ou processo compartilhado.
//
// O frontend pode apontar para qualquer API que implemente o mesmo
// contrato (mesmos endpoints/formatos) -- local, em outro servidor,
// uma versão de staging, etc. Basta trocar o valor abaixo.
//
// Em um ambiente real, esse valor normalmente viria de uma variável de
// build/deploy (ex: gerado pelo pipeline de CI/CD), não editado à mão.

const API_BASE_URL = "http://localhost:5001";