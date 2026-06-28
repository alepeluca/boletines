export default async function handler(req, res) {
  // CORS headers
  res.setHeader('Access-Control-Allow-Credentials', 'true');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,OPTIONS,PATCH,DELETE,POST,PUT');
  res.setHeader('Access-Control-Allow-Headers', 'X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version');

  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }

  try {
    const { q, categories, searchType, desde, hasta, orden } = req.query;

    if (!q) {
      return res.status(400).json({ error: 'Parámetro q requerido' });
    }

    // Fetch del índice CSV
    const csvUrl = 'https://raw.githubusercontent.com/alepeluca/boletines/main/indice_documentos.csv';
    const csvResponse = await fetch(csvUrl);
    
    if (!csvResponse.ok) {
      return res.status(500).json({ error: 'No se pudo cargar el índice' });
    }

    const csvText = await csvResponse.text();
    const docs = parsearCSV(csvText);

    // Parsear categorías
    const catArray = categories ? categories.split(',').map(c => c.trim()) : ['boletines'];
    
    // Compilar regex de búsqueda
    let regex;
    if (searchType === 'endsWith') {
      regex = new RegExp(q + '$', 'i');
    } else if (searchType === 'or') {
      const words = q.split('|').map(w => w.trim()).join('|');
      regex = new RegExp(words, 'i');
    } else {
      regex = new RegExp(q, 'i');
    }

    // Filtrar resultados
    const results = docs.filter(doc => {
      // Filtro de categoría
      if (!catArray.includes(doc.categoria)) return false;

      // Filtro de fecha
      const fecha8 = normalizarFecha(doc.fecha);
      if (fecha8 < desde || fecha8 > hasta) return false;

      // Filtro de búsqueda
      const contenido = (doc.archivo || '') + ' ' + (doc.extra_info || '') + ' ' + (doc.url || '');
      return regex.test(contenido);
    });

    // Ordenar
    results.sort((a, b) => {
      const fa = normalizarFecha(a.fecha);
      const fb = normalizarFecha(b.fecha);
      return orden === 'asc' ? fa.localeCompare(fb) : fb.localeCompare(fa);
    });

    // Limitar a 100 resultados
    const limited = results.slice(0, 100);

    // Formatear respuesta
    const formatted = limited.map(doc => ({
      categoria: doc.categoria,
      archivo: doc.archivo || '',
      url: doc.url || '#',
      fecha: doc.fecha || '',
      pagina: doc.pagina || 1,
      fragmento: doc.extra_info || '',
      datosFecha: {
        sortable: normalizarFecha(doc.fecha),
        display: formatearFecha(doc.fecha)
      }
    }));

    res.status(200).json(formatted);

  } catch (error) {
    console.error('Error en búsqueda:', error);
    res.status(500).json({ error: error.message });
  }
}

function parsearCSV(text) {
  const lines = text.split(/\r?\n/);
  if (lines.length === 0) return [];
  
  const headers = lines[0].split(',').map(h => h.trim().toLowerCase().replace(/^"|"$/g, ''));
  const rows = [];

  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;

    let arr = [];
    let insideQuote = false;
    let entry = '';

    for (let j = 0; j < line.length; j++) {
      const char = line[j];
      if (char === '"') insideQuote = !insideQuote;
      else if (char === ',' && !insideQuote) {
        arr.push(entry.trim());
        entry = '';
      } else {
        entry += char;
      }
    }
    arr.push(entry.trim());

    if (arr.length >= headers.length) {
      let obj = {};
      headers.forEach((h, index) => {
        obj[h] = arr[index] ? arr[index].replace(/^"|"$/g, '') : '';
      });

      obj.categoria = obj.categoria || arr[0] || '';
      let catLow = obj.categoria.toLowerCase();
      if (catLow.includes('bolet')) obj.categoria = 'boletines';
      else if (catLow.includes('lici')) obj.categoria = 'licitaciones';
      else if (catLow.includes('orden')) obj.categoria = 'hcd_orden';
      else if (catLow.includes('taqui')) obj.categoria = 'hcd_taqui';

      obj.archivo = obj.archivo || arr[1];
      obj.url = obj.url || arr[2];
      obj.fecha = obj.fecha || arr[3];
      obj.extra_info = obj.extra_info || arr[4];
      obj.pagina = obj.pagina || arr[5] || '1';

      rows.push(obj);
    }
  }
  return rows;
}

function normalizarFecha(fecha) {
  if (!fecha) return '19000101';
  
  const cleaned = fecha.replace(/[^\d-]/g, '');
  const match = cleaned.match(/^(19[89]\d|20[0123]\d)[-]?([01]\d)[-]?([0-3]\d)$/);
  
  if (match) {
    return match[1] + match[2] + match[3];
  }
  
  const yearMatch = fecha.match(/\b(19[89]\d|20[0123]\d)\b/);
  if (yearMatch) {
    return yearMatch[1] + '0101';
  }
  
  return '19000101';
}

function formatearFecha(fecha) {
  const norm = normalizarFecha(fecha);
  
  if (norm === '19000101') return 'S/F';
  if (norm.length !== 8) return norm;
  
  const year = norm.slice(0, 4);
  const month = norm.slice(4, 6);
  const day = norm.slice(6, 8);
  
  return `${day}/${month}/${year}`;
}
