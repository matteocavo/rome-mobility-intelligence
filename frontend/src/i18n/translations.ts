export type Language = 'it' | 'en';

export interface Translations {
  nav: {
    overview: string;
    currentSituation: string;
    history: string;
    technology: string;
    project: string;
    viewGithub: string;
  };
  status: {
    liveApi: string;
    demoData: string;
    wakingService: string;
    connectingData: string;
    refresh: string;
    refreshing: string;
    preRelease: string;
    dataStatus: string;
    lastUpdate: string;
    analyzedVehicles: string;
    criticalAlerts: string;
  };
  states: {
    noCurrentData: string;
    unavailable: string;
    unavailableHint: string;
    noValue: string;
  };
  disclaimer: {
    badge: string;
    banner: string;
    secondary: string;
  };
  hero: {
    title: string;
    subtitle: string;
    updatedMinutesAgo: (mins: number | string) => string;
    updatedJustNow: string;
    networkStatusBar: string;
    activeTripsLabel: (count: number) => string;
    majorDelayLabel: (count: number) => string;
    typicalDelayLabel: (val: string) => string;
    worstDelayLabel: (val: string) => string;
  };
  search: {
    label: string;
    placeholder: string;
    clear: string;
    suggestionsTitle: string;
    activeVehicles: (count: number) => string;
    viewLine: string;
    noResults: string;
    modes: {
      all: string;
      bus: string;
      tram: string;
    };
  };
  lineDetail: {
    backToAll: string;
    lineTitle: (line: string) => string;
    modeLabel: (mode: string) => string;
    activeTripsCount: (count: number) => string;
    summaryCardTitle: string;
    averageRisk: string;
    maxDelay: string;
    lastUpdate: string;
    scoredVehiclesOnLine: string;
    routeMapTitle: string;
    routeMapSubtitle: string;
    stopsOnMap: string;
    vehiclesOnMap: string;
    technicalDetails: string;
    hideTechnicalDetails: string;
    noCoordinates: string;
    noCoordinatesPlaceholder: string;
  };
  kpi: {
    analyzedTrips: string;
    analyzedTripsSub: string;
    majorDelays: string;
    majorDelaysSub: string;
    medianDelay: string;
    medianDelaySub: string;
    p90Delay: string;
    p90DelaySub: string;
    dataFreshness: string;
    dataFreshnessSub: string;
    highRiskBadge: string;
    nominalBadge: string;
    freshBadge: string;
    staleBadge: string;
  };
  currentSituation: {
    title: string;
    subtitle: string;
    filterMode: string;
    severityFilter: {
      all: string;
      majorOnly: string;
      moderate: string;
      normal: string;
    };
    sort: {
      label: string;
      highestRisk: string;
      currentDelay: string;
      line: string;
    };
    table: {
      line: string;
      type: string;
      vehicleTrip: string;
      nextStop: string;
      observedDelay: string;
      majorDelayRisk: string;
      status: string;
      action: string;
    };
    statuses: {
      normal: string;
      minorDelay: string;
      moderateDelay: string;
      majorDelay: string;
    };
    showingCount: (count: number, total: number) => string;
    noVehiclesFound: string;
    inspector: {
      title: string;
      vehicleId: string;
      targetStop: string;
      stopSeq: string;
      tripId: string;
      observedDelay: string;
      majorRisk: string;
      scheduledSecs: string;
      distanceMeters: string;
      speedKmH: string;
      ruleExplanation: string;
      close: string;
    };
  };
  visualizations: {
    tripStatusTitle: string;
    tripStatusSubtitle: string;
    criticalLinesTitle: string;
    criticalLinesSubtitle: string;
    criticalLinesClickHint: string;
    delayDistTitle: string;
    delayDistSubtitle: string;
    tripsFlagged: (flagged: number, total: number) => string;
  };
  history: {
    title: string;
    subtitle: string;
    archiveLabel: string;
    filterAllLines: string;
    filterMajorOnly: string;
    recentTrendTitle: string;
    majorRateFeedWindow: string;
    table: {
      timestamp: string;
      line: string;
      stop: string;
      arrivalDelay: string;
      riskProbability: string;
      classification: string;
      batch: string;
    };
    pagination: {
      showing: (start: number, end: number, total: number) => string;
      page: (current: number, total: number) => string;
    };
    empty: string;
    loading: string;
  };
  technology: {
    title: string;
    subtitle: string;
    tabs: {
      model: string;
      pipeline: string;
      architecture: string;
      quality: string;
    };
    model: {
      title: string;
      description: string;
      family: string;
      eventTarget: string;
      eventTargetDesc: string;
      thresholdTitle: string;
      thresholdDesc: string;
      metricsTitle: string;
      metricsSubtitle: string;
      metricsNote: string;
      metrics: {
        accuracy: string;
        precision: string;
        recall: string;
        f1: string;
        rocAuc: string;
        avgPrecision: string;
      };
      histogramTitle: string;
      histogramSubtitle: string;
      featuresTitle: string;
      features: {
        dynamicsTitle: string;
        dynamicsDesc: string;
        spatialTitle: string;
        spatialDesc: string;
        historicalTitle: string;
        historicalDesc: string;
      };
    };
    pipeline: {
      title: string;
      steps: {
        step1: { title: string; desc: string };
        step2: { title: string; desc: string };
        step3: { title: string; desc: string };
        step4: { title: string; desc: string };
        step5: { title: string; desc: string };
        step6: { title: string; desc: string };
        step7: { title: string; desc: string };
      };
    };
    architecture: {
      title: string;
      activeLabel: string;
      optionalLabel: string;
      blocks: {
        gtfs: { title: string; subtitle: string; desc: string };
        databricks: { title: string; subtitle: string; desc: string };
        fastapi: { title: string; subtitle: string; desc: string };
        neon: { title: string; subtitle: string; desc: string };
        frontend: { title: string; subtitle: string; desc: string };
      };
      orchestrationTitle: string;
      currentOrchTitle: string;
      currentOrchBadge: string;
      currentOrchDesc: string;
      plannedOrchTitle: string;
      plannedOrchBadge: string;
      plannedOrchDesc: string;
      securityBoundaryTitle: string;
      securityBoundaryDesc: string;
    };
    quality: {
      title: string;
      items: {
        freshness: { title: string; desc: string };
        dedup: { title: string; desc: string };
        idempotence: { title: string; desc: string };
        gate: { title: string; desc: string };
        security: { title: string; desc: string };
      };
    };
  };
  project: {
    title: string;
    lead: string;
    objectiveTitle: string;
    objectiveText: string;
    howItWorksTitle: string;
    howItWorksText: string;
    dataSourceTitle: string;
    dataSourceText: string;
    openSourceTitle: string;
    openSourceText: string;
    authorTitle: string;
    authorName: string;
    authorRole: string;
    authorBio: string;
    disclaimerTitle: string;
    disclaimerText: string;
    dataAttribution: string;
    license: string;
  };
  footer: {
    tagline: string;
    sourceCode: string;
    zeroCostTopology: string;
    disclaimer: string;
    attribution: string;
  };
}

export const translations: Record<Language, Translations> = {
  it: {
    nav: {
      overview: 'Panoramica',
      currentSituation: 'Situazione attuale',
      history: 'Storico',
      technology: 'Tecnologia',
      project: 'Progetto',
      viewGithub: 'GitHub',
    },
    status: {
      liveApi: 'Ultimo snapshot disponibile',
      demoData: 'Dati dimostrativi',
      wakingService: 'Avvio del servizio dati…',
      connectingData: 'Connessione agli ultimi dati disponibili…',
      refresh: 'Aggiorna',
      refreshing: 'Aggiornamento…',
      preRelease: 'v1.0.1',
      dataStatus: 'Stato dati',
      lastUpdate: 'Ultimo aggiornamento',
      analyzedVehicles: 'Mezzi analizzati',
      criticalAlerts: 'Ritardi importanti',
    },
    states: {
      noCurrentData: 'Nessun dato corrente',
      unavailable: 'Dati temporaneamente non disponibili',
      unavailableHint: 'Il servizio dati si sta avviando: riprovo automaticamente.',
      noValue: '—',
    },
    disclaimer: {
      badge: 'Progetto indipendente',
      banner:
        'Progetto indipendente. Non affiliato, approvato o gestito da Roma Capitale, ATAC S.p.A. o altri operatori di trasporto.',
      secondary: 'Elaborazione analitica basata sui feed aperti GTFS e GTFS-Realtime.',
    },
    hero: {
      title: 'Mobilità pubblica a Roma',
      subtitle: 'Stato corrente dei dati di mobilità analizzati dal sistema.',
      updatedMinutesAgo: (mins) => `Aggiornato ${mins} fa`,
      updatedJustNow: 'Aggiornato poco fa',
      networkStatusBar: 'Situazione rete',
      activeTripsLabel: (count) => `${count} osservazioni analizzate`,
      majorDelayLabel: (count) => `${count} con ritardo importante`,
      typicalDelayLabel: (val) => `Ritardo tipico: ${val}`,
      worstDelayLabel: (val) => `Casi critici: ${val}`,
    },
    search: {
      label: 'Cerca la tua linea',
      placeholder: 'Cerca linea o fermata nel campione…',
      clear: 'Cancella',
      suggestionsTitle: 'Linee in servizio',
      activeVehicles: (count) => `${count} osservazioni`,
      viewLine: 'Apri linea',
      noResults: 'Nessuna linea o fermata trovata per questa ricerca.',
      modes: {
        all: 'Tutte le modalità',
        bus: 'Bus',
        tram: 'Tram',
      },
    },
    lineDetail: {
      backToAll: '← Tutte le linee',
      lineTitle: (line) => `Linea ${line}`,
      modeLabel: (mode) => (mode === 'Tram' ? 'Rete Tramviaria' : mode === 'Bus' ? 'Autobus' : '—'),
      activeTripsCount: (count) => `${count} osservazioni correnti`,
      summaryCardTitle: 'Stato della linea',
      averageRisk: 'Rischio medio ritardo',
      maxDelay: 'Ritardo massimo',
      lastUpdate: 'Ultimo aggiornamento',
      scoredVehiclesOnLine: 'Osservazioni correnti su questa linea',
      routeMapTitle: 'Mappa delle fermate della linea',
      routeMapSubtitle: 'Fermate e geometrie verificate da GTFS statico, dove abbinate. Nessuna posizione veicolo.',
      stopsOnMap: 'Fermate rilevate',
      vehiclesOnMap: 'Posizioni veicolo disponibili',
      technicalDetails: 'Dettagli tecnici',
      hideTechnicalDetails: 'Nascondi dettagli',
      noCoordinates: 'Coordinate geografiche non disponibili per questo passaggio.',
      noCoordinatesPlaceholder:
        'Geometria della corsa non disponibile per questa linea. Sono mostrate le fermate da GTFS statico, se disponibili.',
    },
    kpi: {
      analyzedTrips: 'Osservazioni analizzate',
      analyzedTripsSub: 'Campione persistito',
      majorDelays: 'Ritardi importanti',
      majorDelaysSub: 'Rischio di ritardo ≥ 5 min',
      medianDelay: 'Ritardo tipico',
      medianDelaySub: 'Mediana del ritardo osservato',
      p90Delay: 'Ritardi più gravi',
      p90DelaySub: 'P90 del ritardo osservato',
      dataFreshness: 'Ultimo aggiornamento',
      dataFreshnessSub: 'Freschezza dello snapshot',
      highRiskBadge: 'Criticità',
      nominalBadge: 'Regolare',
      freshBadge: 'Recente',
      staleBadge: 'Da aggiornare',
    },
    currentSituation: {
      title: 'Situazione attuale',
      subtitle: 'Puntualità e stima del rischio di ritardo sulle osservazioni trip × fermata dell’ultimo snapshot disponibile.',
      filterMode: 'Modalità:',
      severityFilter: {
        all: 'Tutti gli stati',
        majorOnly: 'Rischio elevato (≥5m)',
        moderate: 'Rischio moderato',
        normal: 'Rischio contenuto',
      },
      sort: {
        label: 'Ordina per:',
        highestRisk: 'Rischio più alto',
        currentDelay: 'Ritardo attuale',
        line: 'Linea',
      },
      table: {
        line: 'Linea',
        type: 'Tipo',
        vehicleTrip: 'Mezzo / Corsa',
        nextStop: 'Fermata osservata',
        observedDelay: 'Ritardo osservato',
        majorDelayRisk: 'Rischio ritardo (≥5m)',
        status: 'Stato',
        action: 'Dettagli',
      },
      statuses: {
        normal: 'Regolare',
        minorDelay: 'Ritardo lieve',
        moderateDelay: 'Ritardo moderato',
        majorDelay: 'Ritardo importante',
      },
      showingCount: (count, total) => `Mostrati ${count} su ${total} mezzi analizzati`,
      noVehiclesFound: 'Nessun mezzo corrisponde ai filtri selezionati.',
      inspector: {
        title: 'Telemetria operativa del veicolo',
        vehicleId: 'Identificativo mezzo',
        targetStop: 'Fermata osservata',
        stopSeq: 'Sequenza fermata',
        tripId: 'Identificativo corsa (GTFS)',
        observedDelay: 'Ritardo rilevato al passaggio precedente',
        majorRisk: 'Probabilità di ritardo ≥ 5 minuti',
        scheduledSecs: 'Tempo previsto fermata successiva',
        distanceMeters: 'Distanza alla fermata',
        speedKmH: 'Velocità istantanea',
        ruleExplanation:
          'Criterio decisionale: la soglia operativa è calibrata a 0.35. I mezzi che superano questa probabilità vengono segnalati per rischio ritardo rilevante.',
        close: 'Chiudi scheda',
      },
    },
    visualizations: {
      tripStatusTitle: 'Stato dei ritardi osservati',
      tripStatusSubtitle: 'Distribuzione sull’intera popolazione scoring corrente.',
      criticalLinesTitle: 'Linee con maggiore rischio di ritardo',
      criticalLinesSubtitle: 'Percentuale di osservazioni con probabilità elevata di ritardo importante.',
      criticalLinesClickHint: 'Clicca su una linea per visualizzarne la scheda.',
      delayDistTitle: 'Distribuzione dei ritardi',
      delayDistSubtitle: 'Intervalli di ritardo rilevati rispetto all’orario di programma.',
      tripsFlagged: (flagged, total) => `${flagged} osservazioni con ritardo importante su ${total}`,
    },
    history: {
      title: 'Storico delle osservazioni',
      subtitle: 'Tracciamento temporale delle condizioni e archivio delle osservazioni calcolate.',
      archiveLabel: 'Archivio PostgreSQL',
      filterAllLines: 'Tutte le linee',
      filterMajorOnly: 'Solo ritardi importanti',
      recentTrendTitle: 'Andamento ritardi per fascia oraria',
      majorRateFeedWindow: 'Quota di osservazioni con ritardi importanti per finestra oraria',
      table: {
        timestamp: 'Data / Ora',
        line: 'Linea',
        stop: 'Fermata di riferimento',
        arrivalDelay: 'Ritardo registrato',
        riskProbability: 'Probabilità ritardo',
        classification: 'Esito modello',
        batch: 'Batch elaborazione',
      },
      pagination: {
        showing: (start, end, total) => `Visualizzati ${start}–${end} di ${total} record archiviati`,
        page: (current, total) => `Pagina ${current} di ${total}`,
      },
      empty: 'Nessun dato storico trovato con i filtri attuali.',
      loading: 'Caricamento archivio storico…',
    },
    technology: {
      title: 'Tecnologia e metodologia',
      subtitle:
        'Approfondimento tecnico sull’ingegneria dei dati, il modello di machine learning e l’infrastruttura a costo zero.',
      tabs: {
        model: 'Modello predittivo',
        pipeline: 'Pipeline dati',
        architecture: 'Architettura cloud',
        quality: 'Governance & Qualità',
      },
      model: {
        title: 'Classificazione operativa dei ritardi',
        description:
          'Il sistema stima se un mezzo in transito subirà un ritardo significativo (≥ 5 minuti) alla fermata successiva, fornendo un segnale tempestivo rispetto al normale monitoraggio reattivo.',
        family: 'Algoritmo: HistGradientBoostingClassifier',
        eventTarget: 'Obiettivo di previsione',
        eventTargetDesc: 'Evento target: target_realized_next_stop_delay_seconds ≥ 300 secondi (5 minuti).',
        thresholdTitle: 'Calibrazione della soglia operativa (0.35)',
        thresholdDesc:
          'Nei contesti di dispacciamento del trasporto pubblico, una soglia standard del 50% causerebbe la perdita di troppi ritardi critici. Per questo la decisione operativa usa una soglia più bassa: soglia 0,35 selezionata sul validation set per massimizzare l\'F1.',
        metricsTitle: 'Metriche convalidate sul set di test',
        metricsSubtitle: 'Valutazione su holdout temporale separato, valutato una sola volta',
        metricsNote: 'Metriche convalidate della versione del modello operativo:',
        metrics: {
          accuracy: 'Accuratezza: 95.65%',
          precision: 'Precisione: 78.42%',
          recall: 'Richiamo (Recall): 79.91%',
          f1: 'Punteggio F1: 0.7916',
          rocAuc: 'ROC-AUC: 0.9717',
          avgPrecision: 'Precisione media (PR-AUC): 0.8742',
        },
        histogramTitle: 'Istogramma della probabilità di ritardo',
        histogramSubtitle:
          'Distribuzione delle probabilità calcolate con evidenza della soglia decisionale 0.35.',
        featuresTitle: '47 variabili ingegnerizzate (Feature Contract)',
        features: {
          dynamicsTitle: '1. Dinamica dei ritardi e lag temporali',
          dynamicsDesc:
            'Ritardo fermata attuale, ritardi ai passaggi lag-1, lag-2 e lag-3, media mobile a 3 fermate, deviazione standard e accelerazione del ritardo.',
          spatialTitle: '2. Topografia e movimento GTFS',
          spatialDesc:
            'Secondi programmati alla prossima fermata, distanza residua in metri, velocità istantanea, direzione (bearing) e sequenza fermata.',
          historicalTitle: '3. Medie storiche e avvisi di servizio',
          historicalDesc:
            'Ritardo medio storico per linea, per fermata e per ora del giorno, presenza di cantieri, deviazioni o avvisi di servizio attivi.',
        },
      },
      pipeline: {
        title: 'Pipeline dati end-to-end',
        steps: {
          step1: { title: '01. Feed GTFS & RT', desc: 'Acquisizione degli orari statici e dei feed operativi GTFS-Realtime' },
          step2: { title: '02. Lakehouse Databricks', desc: 'Ingestione Bronze e Silver su tabelle Delta' },
          step3: { title: '03. Feature Engineering', desc: 'Generazione delle 47 feature con contratto vincolato' },
          step4: { title: '04. Modello predittivo', desc: 'Inferenza rapida con HistGradientBoosting' },
          step5: { title: '05. API FastAPI', desc: 'Microservizio stateless per servire le risposte' },
          step6: { title: '06. PostgreSQL Neon', desc: 'Persistenza storica e tracciabilità delle osservazioni' },
          step7: { title: '07. Dashboard civica', desc: 'Interfaccia utente web reattiva e accessibile' },
        },
      },
      architecture: {
        title: 'Architettura cloud a costo zero',
        activeLabel: 'Pipeline attiva in produzione',
        optionalLabel: 'Pianificato / Opzionale',
        blocks: {
          gtfs: {
            title: '01 • Sorgente Dati',
            subtitle: 'Open Data Roma Mobilità',
            desc: 'Posizioni veicoli e trip updates pubblici della rete di superficie.',
          },
          databricks: {
            title: '02 • Databricks Free Edition',
            subtitle: 'Feature Store & Delta Lake',
            desc: 'Elaborazione scalabile delle tabelle delta bronze/silver e feature lagging.',
          },
          fastapi: {
            title: '03 • FastAPI su Render',
            subtitle: 'Microservizio di inferenza',
            desc: 'Container Python stateless ospitato su piano free con risveglio automatico.',
          },
          neon: {
            title: '04 • Neon PostgreSQL',
            subtitle: 'Database serverless',
            desc: 'Archiviazione storica delle predizioni con autospegnimento a costo zero.',
          },
          frontend: {
            title: '05 • Frontend React',
            subtitle: 'Cruscotto pubblico',
            desc: 'Applicazione web ottimizzata per la consultazione da desktop e mobile.',
          },
        },
        orchestrationTitle: 'Strategia di orchestrazione',
        currentOrchTitle: 'ORCHESTRAZIONE ATTIVA TEMPORANEA',
        currentOrchBadge: 'GitHub Actions',
        currentOrchDesc:
          'Orchestrazione temporanea tramite GitHub Actions, configurata ogni 30 minuti (17,47 * * * *). BEST-EFFORT TEMPORARY FALLBACK: la delivery a 30 minuti non è garantita.',
        plannedOrchTitle: 'ORCHESTRAZIONE OPZIONALE / PIANIFICATA',
        plannedOrchBadge: 'n8n Community su OCI',
        plannedOrchDesc:
          'Flusso containerizzato n8n predisposto per Oracle Cloud Always Free (e2-micro 1GB RAM) con Caddy, per automazioni avanzate e webhook.',
        securityBoundaryTitle: 'Sicurezza e integrità del perimetro frontend',
        securityBoundaryDesc:
          'Il frontend comunica esclusivamente tramite endpoint pubblici anonimi in sola lettura. Credenziali di servizio, token Databricks e chiavi di accesso al database risiedono interamente sul server e non vengono mai inclusi nel codice del browser.',
      },
      quality: {
        title: 'Data Governance e Affidabilità',
        items: {
          freshness: {
            title: 'Controllo di obsolescenza (Feed Freshness)',
            desc: 'I feed con timestamp non aggiornati vengono contrassegnati per evitare di mostrare previsioni non allineate alla situazione attuale.',
          },
          dedup: {
            title: 'Deduplicazione delle osservazioni',
            desc: 'Identificazione univoca per trip_id, stop_sequence e veicolo per impedire conteggi multipli del medesimo passaggio.',
          },
          idempotence: {
            title: 'Persistenza idempotente',
            desc: 'I batch di salvataggio su PostgreSQL utilizzano clausole ON CONFLICT per garantire consistenza anche in caso di retry automatici.',
          },
          gate: {
            title: 'Gate di validazione temporale',
            desc: 'Verifica della coerenza tra data del servizio e timestamp del feed per scartare osservazioni corrotte.',
          },
          security: {
            title: 'Artefatto modello protetto',
            desc: 'L’integrità del modello è verificata tramite hash SHA-256 del manifesto delle feature senza esporre percorsi interni.',
          },
        },
      },
    },
    project: {
      title: 'Il progetto',
      lead: 'Rome Mobility Intelligence è un progetto indipendente e open source dedicato all’analisi della puntualità e alla previsione dei ritardi del trasporto pubblico a Roma.',
      objectiveTitle: 'Obiettivo',
      objectiveText:
        'La rete di trasporto pubblico di una metropoli storica come Roma è soggetta a forti variabilità causate dal traffico promiscuo, cantieri e strozzature urbane. L’obiettivo è trasformare i dati aperti in un sistema predittivo di allerta precoce per i cittadini e gli operatori.',
      howItWorksTitle: 'Come funziona',
      howItWorksText:
        'I dati orari programmati (GTFS) e i dati operativi correnti (GTFS-Realtime) vengono aggregati ed elaborati tramite un modello di machine learning per stimare la probabilità di ritardo importante alla fermata successiva.',
      dataSourceTitle: 'Dati aperti',
      dataSourceText:
        'La pipeline core usa feed GTFS e GTFS-RT aperti. Il dashboard aggrega la popolazione scoring corrente completa; le tabelle mostrano pagine di osservazioni reali e lo storico persiste in Neon. Nessun dato personale dei passeggeri.',
      openSourceTitle: 'Open source & codice',
      openSourceText:
        'Il codice sorgente di Rome Mobility Intelligence è rilasciato come open source sotto licenza Apache License 2.0.',
      authorTitle: 'Autore',
      authorName: 'Matteo Cavo',
      authorRole: 'Data & Business Intelligence Analyst',
      authorBio: 'Data Engineering · Applied ML · AI & GenAI Workflows',
      disclaimerTitle: 'Dichiarazione di indipendenza',
      disclaimerText:
        'Progetto indipendente. Non affiliato, approvato o gestito da Roma Capitale, ATAC S.p.A. o altri operatori di trasporto.',
      dataAttribution: 'Dati di trasporto: feed aperti GTFS e GTFS-RT forniti tramite Open Data Roma.',
      license: 'Licenza: Apache License 2.0 Open Source.',
    },
    footer: {
      tagline: 'Rome Mobility Intelligence — Ricerca indipendente e open source',
      sourceCode: 'Codice sorgente su GitHub',
      zeroCostTopology: 'Architettura a costo zero',
      disclaimer: 'Progetto indipendente sul trasporto pubblico di Roma.',
      attribution: 'Attribuzione: dati aperti GTFS e GTFS-Realtime Roma Mobilità.',
    },
  },
  en: {
    nav: {
      overview: 'Overview',
      currentSituation: 'Current Situation',
      history: 'History',
      technology: 'Technology',
      project: 'Project',
      viewGithub: 'GitHub',
    },
    status: {
      liveApi: 'Latest available snapshot',
      demoData: 'Synthetic data',
      wakingService: 'Waking data service…',
      connectingData: 'Connecting to latest data…',
      refresh: 'Refresh',
      refreshing: 'Refreshing…',
      preRelease: 'v1.0.1',
      dataStatus: 'Data status',
      lastUpdate: 'Last updated',
      analyzedVehicles: 'Analyzed vehicles',
      criticalAlerts: 'Major delays',
    },
    states: {
      noCurrentData: 'No current data',
      unavailable: 'Data temporarily unavailable',
      unavailableHint: 'The data service is starting up: retrying automatically.',
      noValue: '—',
    },
    disclaimer: {
      badge: 'Independent project',
      banner:
        'Independent project. Not affiliated with, endorsed by, or operated by Roma Capitale, ATAC S.p.A., or other transport operators.',
      secondary: 'Analytical processing based on open GTFS and GTFS-Realtime feeds.',
    },
    hero: {
      title: 'Rome Public Transport',
      subtitle: 'Current state of the mobility data analyzed by the system.',
      updatedMinutesAgo: (mins) => `Updated ${mins} ago`,
      updatedJustNow: 'Updated just now',
      networkStatusBar: 'Network status',
      activeTripsLabel: (count) => `${count} observations analyzed`,
      majorDelayLabel: (count) => `${count} with major delay`,
      typicalDelayLabel: (val) => `Typical delay: ${val}`,
      worstDelayLabel: (val) => `Critical cases: ${val}`,
    },
    search: {
      label: 'Find your line',
      placeholder: 'Search a route or stop in the sample…',
      clear: 'Clear',
      suggestionsTitle: 'Active lines',
      activeVehicles: (count) => `${count} observations`,
      viewLine: 'View line',
      noResults: 'No routes or stops found for this search.',
      modes: {
        all: 'All modes',
        bus: 'Bus',
        tram: 'Tram',
      },
    },
    lineDetail: {
      backToAll: '← All lines',
      lineTitle: (line) => `Line ${line}`,
      modeLabel: (mode) => (mode === 'Tram' ? 'Tramway' : mode === 'Bus' ? 'Bus' : '—'),
      activeTripsCount: (count) => `${count} current observations`,
      summaryCardTitle: 'Line Status',
      averageRisk: 'Average delay risk',
      maxDelay: 'Maximum delay',
      lastUpdate: 'Last updated',
      scoredVehiclesOnLine: 'Current observations on this route',
      routeMapTitle: 'Route stop map',
      routeMapSubtitle: 'Verified static GTFS stops and geometry where matched. No vehicle positions.',
      stopsOnMap: 'Stops mapped',
      vehiclesOnMap: 'Available vehicle positions',
      technicalDetails: 'Technical details',
      hideTechnicalDetails: 'Hide details',
      noCoordinates: 'Geographic coordinates not available for this stop.',
      noCoordinatesPlaceholder:
        'Route map will be available when geographic data is connected to the public API.',
    },
    kpi: {
      analyzedTrips: 'Analyzed observations',
      analyzedTripsSub: 'Persisted sample',
      majorDelays: 'Major delays',
      majorDelaysSub: 'Risk of delay ≥ 5 min',
      medianDelay: 'Typical delay',
      medianDelaySub: 'Median observed delay',
      p90Delay: 'Worst delays',
      p90DelaySub: 'P90 observed delay',
      dataFreshness: 'Last updated',
      dataFreshnessSub: 'Snapshot freshness',
      highRiskBadge: 'Critical',
      nominalBadge: 'Normal',
      freshBadge: 'Fresh',
      staleBadge: 'Needs refresh',
    },
    currentSituation: {
      title: 'Current Situation',
      subtitle: 'Punctuality and estimated major-delay risk over the trip × stop observations of the latest available snapshot.',
      filterMode: 'Mode:',
      severityFilter: {
        all: 'All statuses',
        majorOnly: 'High risk (≥5m)',
        moderate: 'Moderate risk',
        normal: 'Low risk',
      },
      sort: {
        label: 'Sort by:',
        highestRisk: 'Highest risk',
        currentDelay: 'Current delay',
        line: 'Line',
      },
      table: {
        line: 'Line',
        type: 'Type',
        vehicleTrip: 'Vehicle / Trip',
        nextStop: 'Observed stop',
        observedDelay: 'Observed delay',
        majorDelayRisk: 'Delay risk (≥5m)',
        status: 'Status',
        action: 'Details',
      },
      statuses: {
        normal: 'Normal',
        minorDelay: 'Minor delay',
        moderateDelay: 'Moderate delay',
        majorDelay: 'Major delay',
      },
      showingCount: (count, total) => `Showing ${count} of ${total} analyzed vehicles`,
      noVehiclesFound: 'No vehicles match the selected criteria.',
      inspector: {
        title: 'Vehicle Operational Telemetry',
        vehicleId: 'Vehicle Identifier',
        targetStop: 'Scheduled Next Stop',
        stopSeq: 'Stop Sequence',
        tripId: 'Trip ID (GTFS)',
        observedDelay: 'Observed arrival delay from previous stop',
        majorRisk: 'Probability of delay ≥ 5 minutes',
        scheduledSecs: 'Scheduled seconds to next stop',
        distanceMeters: 'Distance to stop',
        speedKmH: 'Instantaneous speed',
        ruleExplanation:
          'Decision criteria: Operational threshold is calibrated at 0.35. Observations exceeding this probability are flagged for operational risk.',
        close: 'Close card',
      },
    },
    visualizations: {
      tripStatusTitle: 'Observed delay status',
      tripStatusSubtitle: 'Distribution over the complete current scoring population.',
      criticalLinesTitle: 'Lines with Highest Delay Risk',
      criticalLinesSubtitle: 'Share of observations on each line with elevated major-delay probability.',
      criticalLinesClickHint: 'Click any line to view its details.',
      delayDistTitle: 'Delay Distribution',
      delayDistSubtitle: 'Observed delay intervals compared against scheduled timetable.',
      tripsFlagged: (flagged, total) => `${flagged} observations flagged with major delay out of ${total}`,
    },
    history: {
      title: 'Observation History',
      subtitle: 'Temporal tracking of congestion patterns and audited prediction history.',
      archiveLabel: 'PostgreSQL archive',
      filterAllLines: 'All lines',
      filterMajorOnly: 'Only major delays',
      recentTrendTitle: 'Delay trend by time window',
      majorRateFeedWindow: 'Share of major delays per rolling feed window',
      table: {
        timestamp: 'Date / Time',
        line: 'Line',
        stop: 'Reference stop',
        arrivalDelay: 'Observed delay',
        riskProbability: 'Delay probability',
        classification: 'Outcome',
        batch: 'Batch ID',
      },
      pagination: {
        showing: (start, end, total) => `Showing ${start}–${end} of ${total} archived records`,
        page: (current, total) => `Page ${current} of ${total}`,
      },
      empty: 'No historical records match the selected filters.',
      loading: 'Loading historical archive…',
    },
    technology: {
      title: 'Technology & Methodology',
      subtitle:
        'In-depth technical architecture covering data engineering, machine learning modeling, and zero-cost cloud topology.',
      tabs: {
        model: 'Predictive Model',
        pipeline: 'Data Pipeline',
        architecture: 'Cloud Architecture',
        quality: 'Governance & Quality',
      },
      model: {
        title: 'Operational Delay Classification',
        description:
          'The system classifies whether an active transit vehicle will experience a major delay (≥ 5 minutes) at its next scheduled stop, providing an actionable early warning.',
        family: 'Algorithm: HistGradientBoostingClassifier',
        eventTarget: 'Prediction Target',
        eventTargetDesc: 'Event: target_realized_next_stop_delay_seconds ≥ 300 seconds (5 minutes).',
        thresholdTitle: 'Operational Decision Threshold Calibration (0.35)',
        thresholdDesc:
          'In operational dispatching, a default 50% cutoff misses too many major delays. Hence the operational decision uses a lower cutoff: threshold 0.35 selected on the validation set to maximize F1.',
        metricsTitle: 'Validated Test Set Metrics',
        metricsSubtitle: 'Evaluated on a separate temporal holdout, evaluated once',
        metricsNote: 'Validated metrics from the operational model evaluation:',
        metrics: {
          accuracy: 'Accuracy: 95.65%',
          precision: 'Precision: 78.42%',
          recall: 'Recall: 79.91%',
          f1: 'F1 Score: 0.7916',
          rocAuc: 'ROC-AUC: 0.9717',
          avgPrecision: 'Average Precision (PR-AUC): 0.8742',
        },
        histogramTitle: 'Delay Probability Distribution',
        histogramSubtitle:
          'Distribution of calculated probabilities with the operational 0.35 threshold mark.',
        featuresTitle: '47 Engineered Features (Feature Contract)',
        features: {
          dynamicsTitle: '1. Delay Dynamics & Lags',
          dynamicsDesc:
            'Current arrival delay, lag-1, lag-2, and lag-3 stop delays, rolling 3-stop mean, standard deviation, and delay acceleration.',
          spatialTitle: '2. Spatial & Route Topography',
          spatialDesc:
            'Scheduled seconds to next stop, remaining distance in meters, vehicle speed, bearing, and stop sequence position.',
          historicalTitle: '3. Historical Baselines & Alerts',
          historicalDesc:
            'Historical route, stop, and hour-of-day mean delay, active construction, detours, and GTFS service alerts.',
        },
      },
      pipeline: {
        title: 'End-to-End Data Pipeline',
        steps: {
          step1: { title: '01. GTFS & RT Feeds', desc: 'Ingestion of static schedules and current GTFS-Realtime operational feeds' },
          step2: { title: '02. Databricks Lakehouse', desc: 'Bronze and Silver delta lake transformation' },
          step3: { title: '03. Feature Engineering', desc: 'Generation of 47 features under strict schema contract' },
          step4: { title: '04. Predictive Model', desc: 'Fast inference with HistGradientBoostingClassifier' },
          step5: { title: '05. FastAPI Service', desc: 'Stateless microservice delivering read-only predictions' },
          step6: { title: '06. Neon PostgreSQL', desc: 'Historical persistence and trip audit trail' },
          step7: { title: '07. Civic Dashboard', desc: 'Responsive, accessible public analytics frontend' },
        },
      },
      architecture: {
        title: 'Zero-Cost Cloud Architecture',
        activeLabel: 'Active Production Pipeline',
        optionalLabel: 'Planned / Optional',
        blocks: {
          gtfs: {
            title: '01 • Data Source',
            subtitle: 'Open Data Roma Mobilità',
            desc: 'Public GTFS static routes and streaming vehicle position updates.',
          },
          databricks: {
            title: '02 • Databricks Free Edition',
            subtitle: 'Feature Store & Delta Lake',
            desc: 'Scalable processing of bronze/silver delta tables and temporal lag features.',
          },
          fastapi: {
            title: '03 • FastAPI on Render',
            subtitle: 'Inference Microservice',
            desc: 'Stateless Python container hosted on Render free tier with auto-wake handling.',
          },
          neon: {
            title: '04 • Neon PostgreSQL',
            subtitle: 'Serverless Database',
            desc: 'Prediction history storage with automatic scale-to-zero at no marginal cost.',
          },
          frontend: {
            title: '05 • React Frontend',
            subtitle: 'Public Dashboard',
            desc: 'Responsive web application optimized for desktop and mobile devices.',
          },
        },
        orchestrationTitle: 'Orchestration Strategy',
        currentOrchTitle: 'ACTIVE TEMPORARY ORCHESTRATION',
        currentOrchBadge: 'GitHub Actions',
        currentOrchDesc:
          'Temporary GitHub Actions orchestration, configured at a 30-minute cadence (17,47 * * * *). BEST-EFFORT TEMPORARY FALLBACK: 30-minute delivery is not guaranteed.',
        plannedOrchTitle: 'PLANNED / OPTIONAL ORCHESTRATION',
        plannedOrchBadge: 'n8n Community on OCI',
        plannedOrchDesc:
          'Containerized n8n workflow designed for Oracle Cloud Always Free (e2-micro 1GB RAM) with Caddy for advanced webhook automation.',
        securityBoundaryTitle: 'Strict Frontend Security Boundary',
        securityBoundaryDesc:
          'The frontend communicates exclusively via anonymous read-only endpoints. Service API keys, Databricks tokens, and database passwords remain securely on the server and are never included in browser assets.',
      },
      quality: {
        title: 'Data Governance & Reliability',
        items: {
          freshness: {
            title: 'Feed Freshness Validation',
            desc: 'Outdated feed timestamps are flagged to avoid presenting stale predictions as current conditions.',
          },
          dedup: {
            title: 'Trip Deduplication',
            desc: 'Unique key tracking per trip_id, stop_sequence, and vehicle to prevent duplicate scoring records.',
          },
          idempotence: {
            title: 'Idempotent Persistence',
            desc: 'PostgreSQL storage queries use ON CONFLICT clauses to ensure data consistency during retries.',
          },
          gate: {
            title: 'Service-Date Quality Gate',
            desc: 'Strict validation between service date and feed timestamp ensures corrupted entries are discarded.',
          },
          security: {
            title: 'Protected Model Artifact',
            desc: 'Model artifact integrity is verified via SHA-256 manifest hash without exposing internal server paths.',
          },
        },
      },
    },
    project: {
      title: 'The Project',
      lead: 'Rome Mobility Intelligence is an independent open-source project exploring Rome public transport reliability and arrival delay prediction using public data.',
      objectiveTitle: 'Objective',
      objectiveText:
        'The transit network of a historical capital like Rome faces distinct challenges: intricate historic street layouts, traffic bottlenecks, and surge volumes. This project turns open data into an actionable early warning system for commuters and transit engineers.',
      howItWorksTitle: 'How it works',
      howItWorksText:
        'Static timetables (GTFS) and current operational data (GTFS-RT) operational data are processed through an ML model that predicts whether a vehicle will experience a major delay at its upcoming scheduled stop.',
      dataSourceTitle: 'Open data',
      dataSourceText:
        'The core pipeline uses open GTFS and GTFS-RT feeds. The dashboard aggregates the complete current scoring population; tables show pages of real observations and history is persisted in Neon. No passenger personal data.',
      openSourceTitle: 'Open source & license',
      openSourceText:
        'The Rome Mobility Intelligence source code is released as open source under the Apache License 2.0.',
      authorTitle: 'Author',
      authorName: 'Matteo Cavo',
      authorRole: 'Data & Business Intelligence Analyst',
      authorBio: 'Data Engineering · Applied ML · AI & GenAI Workflows',
      disclaimerTitle: 'Independent disclaimer',
      disclaimerText:
        'Independent project. Not affiliated with, endorsed by, or operated by Roma Capitale, ATAC S.p.A., or other transport operators.',
      dataAttribution: 'Transit data: public GTFS and GTFS-Realtime feeds provided via Open Data Roma.',
      license: 'License: Apache License 2.0 Open Source.',
    },
    footer: {
      tagline: 'Rome Mobility Intelligence — Independent open-source research',
      sourceCode: 'Source code on GitHub',
      zeroCostTopology: 'Zero-cost architecture',
      disclaimer: 'Independent project about public transport in Rome.',
      attribution: 'Attribution: Roma Mobilità open GTFS and GTFS-Realtime data.',
    },
  },
};
