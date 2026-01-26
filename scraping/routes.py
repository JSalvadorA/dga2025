from __future__ import annotations

ROUTES = {
    "MUNICIPALIDADES": {
        "levels": {
            "level_1": {
                "button": "ctl00_CPH1_BtnTipoGobierno",
                "list_xpath": None,
                "next_level": "level_2",
            },
            "level_2": {
                # ID original que funcionó para scraping de MUNICIPALIDADES
                "button": "ctl00_CPH1_RptData_ctl02_TD0",
                "list_xpath": None,
                "next_level": "level_3",
            },
            "level_3": {
                "button": "ctl00_CPH1_BtnSubTipoGobierno",
                "list_xpath": None,
                "next_level": "level_4",
            },
            "level_4": {
                "button": "ctl00_CPH1_RptData_ctl01_TD0",
                "list_xpath": None,
                "next_level": "level_5",
            },
            "level_5": {
                "button": "ctl00_CPH1_BtnDepartamento",
                "list_xpath": "//tr[starts-with(@id, 'tr')]",
                "name_xpath": "./td[2]",
                "next_level": "level_6",
            },
            "level_6": {
                "button": "ctl00_CPH1_BtnProvincia",
                "list_xpath": "//tr[starts-with(@id, 'tr')]",
                "name_xpath": "./td[2]",
                "next_level": "level_7",
            },
            "level_7": {
                "button": "ctl00_CPH1_BtnMunicipalidad",
                "list_xpath": None,
                "name_xpath": None,
                "table_id": "ctl00_CPH1_Mt0",
                "next_level": None,
            },
        },
    },
    "SECTORES": {
        "levels": {
            "level_1": {
                "button": "ctl00_CPH1_BtnTipoGobierno",
                "list_xpath": None,
                "next_level": "level_2",
            },
            "level_2": {
                # Selección por texto (más robusto que ID hardcodeado)
                "button_text": "E: GOBIERNO NACIONAL",
                "list_xpath": None,
                "next_level": "level_3",
            },
            "level_3": {
                "button": "ctl00_CPH1_BtnSector",
                "list_xpath": "//tr[starts-with(@id, 'tr')]",
                "name_xpath": "./td[2]",
                "next_level": "level_4",
            },
            "level_4": {
                "button": "ctl00_CPH1_BtnPliego",
                "list_xpath": "//tr[starts-with(@id, 'tr')]",
                "name_xpath": "./td[2]",
                "next_level": "level_5",
            },
            "level_5": {
                "button": "ctl00_CPH1_BtnEjecutora",
                "list_xpath": None,
                "name_xpath": None,
                "table_id": "ctl00_CPH1_Mt0",
                "next_level": None,
            },
        },
    },
    "GOBIERNOS_REGIONALES": {
        "levels": {
            "level_1": {
                "button": "ctl00_CPH1_BtnTipoGobierno",
                "list_xpath": None,
                "next_level": "level_2",
            },
            "level_2": {
                # Selección por texto (más robusto que ID hardcodeado)
                "button_text": "R: GOBIERNOS REGIONALES",
                # La tabla de tipos todavía está visible, saltamos a level_3 que hace clic en Departamento
                "list_xpath": None,
                "next_level": "level_3",
            },
            "level_3": {
                # Clic en botón Departamento para mostrar lista de departamentos
                # ID real: ctl00_CPH1_BtnDepartamentoMeta (con sufijo Meta)
                "button": "ctl00_CPH1_BtnDepartamentoMeta",
                "list_xpath": "//tr[starts-with(@id, 'tr')]",
                "name_xpath": "./td[2]",
                "next_level": "level_4",
            },
            "level_4": {
                "button": "ctl00_CPH1_BtnEjecutora",
                "list_xpath": None,
                "name_xpath": None,
                "table_id": "ctl00_CPH1_Mt0",
                "next_level": None,
            },
        },
    },
}

FILE_CONFIGS = {
    "MUNICIPALIDADES": {
        "ENCABEZADOS_BASE": ["Año", "Departamento", "Provincia"],
    },
    "SECTORES": {
        "ENCABEZADOS_BASE": ["Año", "Sector", "Pliego"],
    },
    "GOBIERNOS_REGIONALES": {
        "ENCABEZADOS_BASE": ["Año", "Departamento"],
    },
}

CATEGORY_BY_ROUTE = {
    "MUNICIPALIDADES": "M. MUNICIPALIDADES",
    "SECTORES": "E. EJECUTORAS DEL GOBIERNO NACIONAL",
    "GOBIERNOS_REGIONALES": "R. EJECUTORAS DEL GOBIERNO REGIONAL",
}
