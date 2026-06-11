#!/usr/bin/env python3
import json
import argparse
import random
import math
import statistics
import html
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)




def extract_players(data):
    # data.json has top-level {"data": [players...]}
    players = {}
    raw_players = data.get('data', data) if isinstance(data, dict) else data
    for p in raw_players:
        name = p.get('fullName') or (p.get('firstName') + ' ' + p.get('surname') if p.get('firstName') else p.get('surname'))
        license_ = p.get('license')
        gender = p.get('gender') or p.get('sex')
        # gather historical results from 'games' entries
        results = []
        for g in p.get('games', []):
            r = g.get('result')
            if isinstance(r, (int, float)):
                results.append(int(r))
        players[license_ or name] = {
            'name': name,
            'license': license_,
            'gender': 'M' if gender == 'M' or gender == 1 else ('F' if gender == 'F' or gender == 2 else None),
            'results': results,
            'total': p.get('total', None)
        }
    return players


def extract_results_list(results_json):
    out = []
    for entry in results_json:
        ds = entry.get('digital_scorecard', {})
        name = ds.get('p1_full_name')
        license_ = ds.get('p1_license')
        gender = ds.get('p1_gender')
        pts = entry.get('result')
        if pts is None:
            continue
        out.append({'name': name, 'license': license_, 'gender': 'M' if gender == 1 else ('F' if gender == 2 else None), 'points': int(pts)})
    return out


def merge_last_event(players, results_list, event_label="LAST"):
    # Add the event result to matching player by license or by name
    for r in results_list:
        key = r['license'] if r['license'] in players else None
        if not key:
            # try matching by normalized name
            for k, v in players.items():
                if v['name'] and r['name'] and r['name'].upper() in v['name'].upper():
                    key = k
                    break
        if not key:
            # create new player entry
            key = r['license'] or r['name']
            if key not in players:
                players[key] = {'name': r['name'], 'license': r['license'], 'gender': r['gender'], 'results': [], 'total': None}
        players[key]['results'].append(r['points'])


def best_n_sum(results, n=9):
    if not results:
        return 0
    return sum(sorted(results, reverse=True)[:n])


def assign_tied_positions(sorted_players, score_key='current_best9'):
    tied = []
    last_score = None
    current_rank = 0
    for index, (key, player) in enumerate(sorted_players, start=1):
        score = player.get(score_key, 0)
        if score != last_score:
            current_rank = index
        rank_str = f"T{current_rank}" if score == last_score and index != current_rank else str(current_rank)
        tied.append({'key': key, 'player': player, 'rank': rank_str, 'score': score})
        last_score = score
    return tied


def load_torneos_file(path):
    events = []
    with open(path, encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    for i in range(0, len(lines) - 1, 2):
        name = lines[i]
        date_text = lines[i + 1]
        try:
            date = datetime.strptime(date_text, '%d-%m-%Y').date()
        except ValueError:
            continue
        events.append({'name': name, 'date': date})
    return events


def get_remaining_tournaments(events, as_of=None):
    if as_of is None:
        as_of = datetime.now().date()
    remaining = [e for e in events if e['date'] > as_of]
    return sorted(remaining, key=lambda e: e['date'])


def build_stats(players):
    # compute per-player mean/std using empirical Bayes shrinkage
    # shrink player means and variances toward the global values when data is scarce
    stats = {}
    all_vals = []
    for v in players.values():
        all_vals.extend(v.get('results', []))
    global_mean = statistics.mean(all_vals) if all_vals else 18
    global_std = statistics.pstdev(all_vals) if all_vals else 5
    global_var = global_std ** 2

    # prior_weight is the equivalent sample size of the prior (tunable)
    prior_weight = 5.0

    for k, v in players.items():
        vals = v.get('results', [])
        n = len(vals)
        if n == 0:
            mean = global_mean
            std = global_std * math.sqrt(5.0)
        else:
            sample_mean = statistics.mean(vals)
            # use population variance estimate (pstdev) as baseline
            if n > 1:
                sample_var = statistics.pstdev(vals) ** 2
            else:
                sample_var = global_var

            # shrink the mean toward the global mean (empirical Bayes / James-Stein style)
            mean = (n * sample_mean + prior_weight * global_mean) / (n + prior_weight)

            # pool variance with prior variance to avoid underestimating variability
            pooled_var = (n * sample_var + prior_weight * global_var) / (n + prior_weight)

            # inflate uncertainty for very small n (factor -> 1 at n>=5)
            inflation = math.sqrt(max(1.0, 5.0 / n))
            std = math.sqrt(pooled_var) * inflation

        stats[k] = {'mean': mean, 'std': max(2.0, std)}
    return stats


def print_section(title, log_file=None):
    lines = [
        '\n' + '=' * len(title),
        title,
        '=' * len(title)
    ]
    for line in lines:
        print(line)
        if log_file:
            log_file.write(line + '\n')


def print_table(headers, rows, aligns=None, log_file=None):
    if aligns is None:
        aligns = ['left'] * len(headers)
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    def fmt(cell, width, align):
        s = str(cell)
        return s.rjust(width) if align == 'right' else s.ljust(width)

    header_line = '  '.join(fmt(headers[i], widths[i], aligns[i]) for i in range(len(headers)))
    separator_line = '  '.join('-' * widths[i] for i in range(len(headers)))
    print(header_line)
    if log_file:
        log_file.write(header_line + '\n')
    print(separator_line)
    if log_file:
        log_file.write(separator_line + '\n')
    for row in rows:
        row_line = '  '.join(fmt(row[i], widths[i], aligns[i]) for i in range(len(headers)))
        print(row_line)
        if log_file:
            log_file.write(row_line + '\n')


def render_html_table(headers, rows, caption=None):
    table = []
    table.append('<div class="table-card">')
    if caption:
        table.append(f'<h3>{html.escape(caption)}</h3>')
    table.append('<div class="table-scroll"><table>')
    table.append('<thead><tr>' + ''.join(f'<th>{html.escape(h)}</th>' for h in headers) + '</tr></thead>')
    table.append('<tbody>')
    for row in rows:
        if isinstance(row, dict):
            row_values = [row.get(h, '') for h in headers]
        else:
            row_values = list(row)
        table.append('<tr>' + ''.join(f'<td>{html.escape(str(cell))}</td>' for cell in row_values) + '</tr>')
    table.append('</tbody></table></div></div>')
    return '\n'.join(table)


def render_html_section(title, content):
    return f"<section class='section-card'><h2>{html.escape(title)}</h2>{content}</section>"


def export_to_html(filename, page_title, sections):
    styles = '''
        body {font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif; background: #eef3f8; color: #1d2939; margin: 0;}
        .page {max-width: 1200px; margin: 0 auto; padding: 24px;}
        header {text-align: center; padding: 24px 0 16px;}
        header h1 {margin: 0; font-size: 2.3rem; letter-spacing: -0.03em;}
        .subtitle {margin: 8px auto 0; color: #475569; font-size: 1rem;}
        .section-card {background: #ffffff; border-radius: 20px; padding: 24px; margin-bottom: 20px; box-shadow: 0 18px 40px rgba(15, 23, 42, 0.08);}
        .info-grid {display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-top: 18px;}
        .info-item {background: #f8fbff; border-radius: 14px; padding: 14px 16px;}
        .info-item span {display: block; color: #64748b; margin-top: 6px;}
        .table-card {margin-top: 16px;}
        .table-scroll {overflow-x: auto;}
        table {width: 100%; border-collapse: collapse; min-width: 540px;}
        th, td {padding: 12px 14px; border-bottom: 1px solid #e2e8f0;}
        th {background: #f1f5f9; color: #0f172a; text-align: left; font-weight: 700;}
        tr:nth-child(even) {background: #fbfcfe;}
        .metric-list {list-style: none; padding: 0; margin: 0;}
        .metric-list li {margin-bottom: 10px;}
        .tag {display: inline-flex; align-items: center; padding: 6px 12px; border-radius: 999px; background: #e0f2fe; color: #0369a1; font-weight: 600;}
    '''
    body = [
        '<!DOCTYPE html>',
        '<html lang="es">',
        '<head>',
        '<meta charset="utf-8">',
        f'<title>{html.escape(page_title)}</title>',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f'<style>{styles}</style>',
        '</head>',
        '<body>',
        '<div class="page">',
        f'<header><h1>{html.escape(page_title)}</h1></header>'
    ]
    body.extend(sections)
    body.append('</div></body></html>')
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join(body))


def monte_carlo_simulate(players, stats, remaining_events=9, sims=10000, count_best=9, prob_play=0.9, exclude_one_game=True, progress_label=None, show_progress=False):
    """Run Monte Carlo simulations to estimate winners and top-point projections.

    Each simulation samples remaining event scores for each player and computes final best-n totals.

    Returns:
      wins_pct, placement_pct, final_totals, cutoff_lists
    """
    if isinstance(remaining_events, list):
        event_weights = remaining_events
    else:
        event_weights = [1.0] * remaining_events

    wins = defaultdict(float)
    player_keys = list(players.keys())

    # store final totals per player per simulation
    final_totals = {k: [] for k in player_keys}
    # counters for topN membership
    top_counts = {k: {'TOP50': 0, 'TOP20': 0, 'TOP10': 0, 'TOP3': 0} for k in player_keys}
    # store per-simulation cutoff thresholds
    cutoff_lists = {'TOP50': [], 'TOP20': [], 'TOP10': [], 'TOP3': [], 'TOP1': []}

    update_every = max(1, sims // 50)
    if show_progress:
        label = progress_label or 'Simulando'
        sys.stdout.write(f"{label}: 0/{sims}")
        sys.stdout.flush()

    for s in range(sims):
        totals = {}
        for k in player_keys:
            historic = list(players[k]['results'])
            # simulate each remaining event with probability prob_play
            for weight in event_weights:
                if random.random() <= prob_play:
                    m = stats[k]['mean']
                    sd = stats[k]['std']
                    val = int(round(random.gauss(m, sd)))
                    val = max(0, min(40, val))
                    if weight == 1.0:
                        # En simulaciones de pruebas restantes, máximo 28 puntos por prueba normal.
                        val = min(val, 28)
                    else:
                        val = int(round(val * weight))
                        # La última prueba cuenta doble y su puntuación final no puede superar 50.
                        val = min(val, 50)
                    historic.append(val)
            total_pts = best_n_sum(historic, count_best)
            totals[k] = total_pts
            final_totals[k].append(total_pts)

        if show_progress and ((s + 1) % update_every == 0 or s == sims - 1):
            label = progress_label or 'Simulando'
            sys.stdout.write(f"\r{label}: {s + 1}/{sims} ({int(((s + 1) / sims) * 100)}%)")
            sys.stdout.flush()

        # determine eligible players first (exclude players with only 1 historical game if requested)
        if exclude_one_game:
            eligible = [k for k in player_keys if len(players[k]['results']) != 1]
        else:
            eligible = player_keys

        # compute top-N thresholds only among eligible players
        eligible_scores = [totals[k] for k in eligible]
        eligible_scores_sorted = sorted(eligible_scores, reverse=True)
        if not eligible_scores_sorted:
            continue

        def thresh(n):
            idx = min(n, len(eligible_scores_sorted)) - 1
            return eligible_scores_sorted[idx]

        t50 = thresh(50)
        t20 = thresh(20)
        t10 = thresh(10)
        t3 = thresh(3)

        # record cutoffs for this simulation
        cutoff_lists['TOP50'].append(t50)
        cutoff_lists['TOP20'].append(t20)
        cutoff_lists['TOP10'].append(t10)
        cutoff_lists['TOP3'].append(t3)

        # count top-N memberships only for eligible players
        for k in eligible:
            if totals[k] >= t50:
                top_counts[k]['TOP50'] += 1
            if totals[k] >= t20:
                top_counts[k]['TOP20'] += 1
            if totals[k] >= t10:
                top_counts[k]['TOP10'] += 1
            if totals[k] >= t3:
                top_counts[k]['TOP3'] += 1

        # determine winners among eligible
        eligible_scores_map = {k: totals[k] for k in eligible} if eligible else {}
        if eligible_scores_map:
            max_score = max(eligible_scores_map.values())
            # append TOP1 cutoff (max score among eligible)
            cutoff_lists['TOP1'].append(max_score)
            winners = [k for k, sc in eligible_scores_map.items() if sc == max_score]
            for w in winners:
                wins[w] += 1.0 / len(winners)
        else:
            cutoff_lists['TOP1'].append(0)

    if show_progress:
        sys.stdout.write('\n')

    # compute percentages
    pct = {k: 100.0 * v / sims for k, v in wins.items()}
    placement_pct = {}
    for k in player_keys:
        placement_pct[k] = {
            'TOP50': top_counts[k]['TOP50'] / sims * 100.0,
            'TOP20': top_counts[k]['TOP20'] / sims * 100.0,
            'TOP10': top_counts[k]['TOP10'] / sims * 100.0,
            'TOP3': top_counts[k]['TOP3'] / sims * 100.0,
            'WIN': pct.get(k, 0.0)
        }

    return pct, placement_pct, final_totals, cutoff_lists


simulate = monte_carlo_simulate

def log_print(message, log_file=None):
    print(message)
    if log_file:
        log_file.write(message + '\n')


def main():
    parser = argparse.ArgumentParser(description='Analizador de circuito 5a Categoria Catalunya 2026')
    parser.add_argument('player', help='Nombre o licencia del jugador a analizar')
    parser.add_argument('--sims', type=int, default=10000, help='Número de simulaciones (default 10000)')
    parser.add_argument('--remaining', type=int, default=9, help='Número de pruebas restantes a simular si no hay torneos.txt')
    parser.add_argument('--sab-file', default='resultados_sabado.json', help='Archivo opcional de resultados de sábado')
    parser.add_argument('--dom-file', default='resultados_domingo.json', help='Archivo opcional de resultados de domingo')
    parser.add_argument('--torneos-file', default='torneos.txt', help='Archivo con el listado completo de torneos jugados y por jugar')
    args = parser.parse_args()

    current_path = Path(__file__).resolve().parent
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    player_sanitized = args.player.replace(' ', '_').replace('/', '_')
    output_path = current_path / f'resultados_{player_sanitized}_{timestamp}.html'

    data_path = current_path / 'data.json'
    if not data_path.exists():
        print(f'No se encontró el archivo de datos principal: {data_path}')
        return

    data = load_json(str(data_path))
    players = extract_players(data)
    source_notes = []
    last_results = []
    for label, filename in [('Sábado', args.sab_file), ('Domingo', args.dom_file)]:
        if not filename:
            source_notes.append((label, 'No se aplicó'))
            continue
        file_path = current_path / filename
        if file_path.exists():
            results_json = load_json(str(file_path))
            last_results.extend(extract_results_list(results_json))
            source_notes.append((label, f'Cargado desde {filename}'))
        else:
            source_notes.append((label, f'No encontrado ({filename})'))

    torneos_path = current_path / args.torneos_file
    remaining_events_info = []
    event_weights = []
    if torneos_path.exists():
        torneos = load_torneos_file(str(torneos_path))
        remaining = get_remaining_tournaments(torneos)
        if remaining:
            for i, event in enumerate(remaining):
                weight = 2.0 if i == len(remaining) - 1 else 1.0
                event_weights.append(weight)
                remaining_events_info.append([event['name'], event['date'].strftime('%d/%m/%Y'), '2x' if weight == 2.0 else '1x'])
            source_notes.append(('Torneos', f'Usado {args.torneos_file} con {len(remaining)} torneos restantes'))
        else:
            source_notes.append(('Torneos', f'{args.torneos_file} existe pero no hay torneos futuros'))
            event_weights = [1.0] * args.remaining
    else:
        event_weights = [1.0] * args.remaining
        source_notes.append(('Torneos', f'No encontrado {args.torneos_file}, usando --remaining={args.remaining}'))

    merge_last_event(players, last_results, event_label='COSTA_BRAVA')

    players_all = players
    players_by_gender = {
        'M': {k: v for k, v in players_all.items() if v.get('gender') == 'M'},
        'F': {k: v for k, v in players_all.items() if v.get('gender') == 'F'}
    }

    for v in players_all.values():
        v['current_best9'] = best_n_sum(v['results'], 9)

    ranking_general = sorted(players_all.items(), key=lambda kv: kv[1]['current_best9'], reverse=True)
    ranking_male = sorted(players_by_gender['M'].items(), key=lambda kv: kv[1]['current_best9'], reverse=True)
    ranking_female = sorted(players_by_gender['F'].items(), key=lambda kv: kv[1]['current_best9'], reverse=True)

    ranking_general_tied = assign_tied_positions(ranking_general)
    ranking_male_tied = assign_tied_positions(ranking_male)
    ranking_female_tied = assign_tied_positions(ranking_female)

    # find queried player key in the full dataset
    query = args.player.upper()
    query_key = None
    for k, v in players_all.items():
        if (v.get('license') and v['license'].upper() == query) or (v.get('name') and query in v['name'].upper()):
            query_key = k
            break

    if query_key is None:
        print(f'Jugador no encontrado: {args.player}')
        return

    query_gender = players_all[query_key].get('gender')
    group_players = players_by_gender.get(query_gender, {}) if query_gender in ('M', 'F') else {}
    if not group_players:
        print(f'No hay suficientes datos del sexo del jugador ({query_gender}) para el análisis por categorías.')
        return

    ranking_group = sorted(group_players.items(), key=lambda kv: kv[1]['current_best9'], reverse=True)
    ranking_group_tied = assign_tied_positions(ranking_group)
    rank_pos_general = next((item['rank'] for item in ranking_general_tied if item['key'] == query_key), None)
    rank_pos_group = next((item['rank'] for item in ranking_group_tied if item['key'] == query_key), None)

    current_name = players_all[query_key]['name']
    current_lic = players_all[query_key].get('license', 'N/A')
    print_section('Resumen del jugador')
    print(f'Jugador: {current_name} ({current_lic})')
    print(f'Posición actual general: {rank_pos_general}')
    print(f'Posición actual en categoría {"Masculina" if query_gender == "M" else "Femenina"}: {rank_pos_group}')
    print(f'Puntos actuales (mejores 9): {players_all[query_key]["current_best9"]}')

    # build stats and simulate using Monte Carlo separately for each sex
    simulations_by_gender = {}
    for gender, group in players_by_gender.items():
        if group:
            stats = build_stats(group)
            simulations_by_gender[gender] = monte_carlo_simulate(
                group,
                stats,
                remaining_events=event_weights if event_weights else args.remaining,
                sims=args.sims,
                count_best=9,
                prob_play=0.9,
                progress_label=f'Sim {gender}',
                show_progress=True
            )
        else:
            simulations_by_gender[gender] = ({}, {}, {}, {})

    wins_pct, placement_pct, final_totals, cutoff_lists = simulations_by_gender[query_gender]
    placements_by_gender = {
        gender: sim[1] for gender, sim in simulations_by_gender.items()
    }

    # compute PRE (Puntos Reemplazables Esperados) and current 9th best for each player
    pre_metrics = {}
    for k, v in players_all.items():
        current_best9 = v.get('current_best9', 0)
        current_results = v.get('results', [])
        current_ninth = sorted(current_results, reverse=True)[8] if len(current_results) >= 9 else 0
        holes_remaining = max(0, 9 - len(current_results))
        vals = final_totals.get(k, [])
        improvements = [max(0, total - current_best9) for total in vals] if vals else []
        if improvements:
            sorted_impr = sorted(improvements)
            p90_idx = min(len(sorted_impr) - 1, max(0, int(0.9 * len(sorted_impr)) - 1))
            pre_mean = statistics.mean(improvements)
            pre_p90 = sorted_impr[p90_idx]
        else:
            pre_mean = 0.0
            pre_p90 = 0.0
        pre_metrics[k] = {
            'pre_mean': pre_mean,
            'pre_p90': pre_p90,
            'ninth_best': current_ninth,
            'holes_remaining': holes_remaining
        }

    # compute simulated positions for the queried player within their category
    position_samples = []
    if final_totals:
        for s in range(args.sims):
            sim_scores = sorted(
                [(k, final_totals[k][s]) for k in final_totals],
                key=lambda x: x[1],
                reverse=True
            )
            last_score = None
            rank = 0
            for idx, (k, score) in enumerate(sim_scores, start=1):
                if score != last_score:
                    rank = idx
                if k == query_key:
                    position_samples.append(rank)
                    break
                last_score = score

    if position_samples:
        avg_position = statistics.mean(position_samples)
        best_position = min(position_samples)
        worst_position = max(position_samples)
    else:
        avg_position = 0.0
        best_position = 0
        worst_position = 0

    # print top candidates by win probability
    top_win = sorted(wins_pct.items(), key=lambda x: x[1], reverse=True)[:20]
    print_section('Probabilidades de victoria (TOP 20)')
    print('PRE = Puntos Reemplazables Esperados; indica cuánto puede mejorar un jugador en sus mejores 9 resultados.')
    print('Eficiencia PRE = TOP3 % / PRE medio; mide qué tan eficiente es el potencial de mejora en relación con la probabilidad de entrar en el podio.')
    rows = []
    top_win_rows = []
    for lic, w in top_win:
        p = players_all.get(lic, {})
        placements = placement_pct.get(lic, {})
        metrics = pre_metrics.get(lic, {})
        current_best9 = p.get('current_best9', 0)
        pre_p90 = metrics.get('pre_p90', 0.0)
        actual_plus_pre90 = current_best9 + pre_p90
        pre_mean = metrics.get('pre_mean', 0.0)
        pre_eff = (placements.get('TOP3', 0) / pre_mean) if pre_mean > 0 else 0.0
        row = [
            p.get('name', '?'),
            f'{w:.2f}%',
            f"{placements.get('TOP3', 0):.2f}%",
            f"{placements.get('TOP10', 0):.2f}%",
            f"{placements.get('TOP20', 0):.2f}%",
            f"{pre_mean:.1f}",
            f"{pre_p90:.1f}",
            f"{pre_eff:.2f}",
            f"{actual_plus_pre90:.1f}",
            str(metrics.get('ninth_best', 0)),
            str(metrics.get('holes_remaining', 0))
        ]
        rows.append(row)
        top_win_rows.append({
            'Jugador': p.get('name', '?'),
            'Win %': f'{w:.2f}%',
            'TOP3 %': f"{placements.get('TOP3', 0):.2f}%",
            'TOP10 %': f"{placements.get('TOP10', 0):.2f}%",
            'TOP20 %': f"{placements.get('TOP20', 0):.2f}%",
            'PRE medio': f"{pre_mean:.1f}",
            'PRE P90': f"{pre_p90:.1f}",
            'Eficiencia PRE': f"{pre_eff:.2f}",
            'Actual + PRE P90': f"{actual_plus_pre90:.1f}",
            '9ª mejor': str(metrics.get('ninth_best', 0)),
            'Huecos': str(metrics.get('holes_remaining', 0))
        })
    rows = sorted(rows, key=lambda r: float(r[2].strip('%')), reverse=True)
    top_win_rows = sorted(top_win_rows, key=lambda d: float(d['TOP3 %'].strip('%')), reverse=True)
    print_table(
        ['Jugador', 'Win', 'TOP3', 'TOP10', 'TOP20', 'PRE medio', 'PRE P90', 'Eficiencia PRE', 'Actual + PRE P90', '9ª mejor', 'Huecos'],
        rows,
        aligns=['left', 'right', 'right', 'right', 'right', 'right', 'right', 'right', 'right', 'right', 'right']
    )

    # mostrar estadísticas de puntos finales para los ganadores predichos (top candidates)
    print_section('Puntos finales predichos para candidatos')
    rows = []
    points_projection_rows = []
    for lic, w in top_win:
        if w <= 0:
            continue
        vals = final_totals.get(lic, [])
        if not vals:
            continue
        mean_pts = statistics.mean(vals)
        std_pts = statistics.pstdev(vals) if len(vals) > 1 else 0.0
        median_pts = statistics.median(vals)
        vals_sorted = sorted(vals)
        p10 = vals_sorted[max(0, int(0.1 * len(vals_sorted)) - 1)]
        p90 = vals_sorted[min(len(vals_sorted) - 1, int(0.9 * len(vals_sorted)) - 1)]
        row = [
            players.get(lic, {}).get('name', '?'),
            f'{mean_pts:.2f}',
            f'{median_pts:.2f}',
            f'{std_pts:.2f}',
            f'{p10:.2f}',
            f'{p90:.2f}'
        ]
        rows.append(row)
        points_projection_rows.append({
            'Jugador': players.get(lic, {}).get('name', '?'),
            'Media': f'{mean_pts:.2f}',
            'Mediana': f'{median_pts:.2f}',
            'SD': f'{std_pts:.2f}',
            'P10': f'{p10:.2f}',
            'P90': f'{p90:.2f}'
        })
    points_projection_rows = sorted(points_projection_rows, key=lambda d: float(d['Mediana']), reverse=True)
    if rows:
        rows = sorted(rows, key=lambda r: float(r[2]), reverse=True)
        print_table(['Jugador', 'Media', 'Mediana', 'SD', 'P10', 'P90'], rows, aligns=['left', 'right', 'right', 'right', 'right', 'right'])
    else:
        print('No hay datos suficientes para mostrar predicciones de puntos.')

    # show queried player's chances
    qp = placement_pct.get(query_key, {})
    print_section(f'Estadísticas de {players[query_key]['name']}')
    rows = [
        ['TOP50', f"{qp.get('TOP50', 0):.1f}%"],
        ['TOP20', f"{qp.get('TOP20', 0):.1f}%"],
        ['TOP10', f"{qp.get('TOP10', 0):.1f}%"],
        ['TOP3', f"{qp.get('TOP3', 0):.1f}%"],
        ['Ganar', f"{qp.get('WIN', 0):.2f}%"],
        ['Posición media', f"{avg_position:.2f}"],
        ['Mejor posición', str(best_position)],
        ['Peor posición', str(worst_position)]
    ]
    print_table(['Categoría', 'Probabilidad'], rows, aligns=['left', 'right'])
    query_stats_rows = rows

    # final points distribution for queried player
    q_final = final_totals.get(query_key, [])
    distribution_rows = []
    player_distribution_rows = []
    if q_final:
        mean_pts = statistics.mean(q_final)
        std_pts = statistics.pstdev(q_final) if len(q_final) > 1 else 0.0
        median_pts = statistics.median(q_final)
        q_final_sorted = sorted(q_final)
        p10 = q_final_sorted[max(0, int(0.1 * len(q_final_sorted)) - 1)]
        p90 = q_final_sorted[min(len(q_final_sorted) - 1, int(0.9 * len(q_final_sorted)) - 1)]
        print_section('Distribución de puntos finales')
        print_table(
            ['Métrica', 'Valor'],
            [
                ['Media', f'{mean_pts:.1f}'],
                ['Desv. típica', f'{std_pts:.1f}'],
                ['Mediana', f'{median_pts:.1f}'],
                ['P10', str(p10)],
                ['P90', str(p90)],
                ['Mínimo', str(min(q_final))],
                ['Máximo', str(max(q_final))]
            ],
            aligns=['left', 'right']
        )
        player_distribution_rows = [
            {'Métrica': 'Media', 'Valor': mean_pts},
            {'Métrica': 'Desv. típica', 'Valor': std_pts},
            {'Métrica': 'Mediana', 'Valor': median_pts},
            {'Métrica': 'P10', 'Valor': p10},
            {'Métrica': 'P90', 'Valor': p90},
            {'Métrica': 'Mínimo', 'Valor': min(q_final)},
            {'Métrica': 'Máximo', 'Valor': max(q_final)}
        ]

    # Estimated cutoff distributions at end of circuit (from simulations)
    cutoff_rows = []
    if cutoff_lists:
        print_section('Cortes estimados al final del circuito')
        rows = []
        for label in ['TOP50', 'TOP20', 'TOP10', 'TOP3', 'TOP1']:
            vals = cutoff_lists.get(label, [])
            if not vals:
                continue
            mean_v = statistics.mean(vals)
            med_v = statistics.median(vals)
            sd_v = statistics.pstdev(vals) if len(vals) > 1 else 0.0
            sorted_v = sorted(vals)
            p10 = sorted_v[max(0, int(0.1 * len(sorted_v)) - 1)]
            p90 = sorted_v[min(len(sorted_v) - 1, int(0.9 * len(sorted_v)) - 1)]
            rows.append([label, f'{mean_v:.1f}', f'{med_v:.1f}', f'{sd_v:.1f}', str(p10), str(p90)])
            cutoff_rows.append({
                'Corte': label,
                'Media': f'{mean_v:.2f}',
                'Mediana': f'{med_v:.2f}',
                'SD': f'{sd_v:.2f}',
                'P10': f'{p10:.2f}',
                'P90': f'{p90:.2f}'
            })
        if rows:
            print_table(['Corte', 'Media', 'Mediana', 'SD', 'P10', 'P90'], rows, aligns=['left', 'right', 'right', 'right', 'right', 'right'])

    print('\nTop 10 actual general (tras sumar la última prueba):')
    for item in ranking_general_tied[:10]:
        print(f"{item['rank']:>3} {item['player'].get('name','?')} - {item['score']} pts")

    if ranking_male_tied:
        print('\nTop 10 masculino actual:')
        for item in ranking_male_tied[:10]:
            print(f"{item['rank']:>3} {item['player'].get('name','?')} - {item['score']} pts")

    if ranking_female_tied:
        print('\nTop 10 femenino actual:')
        for item in ranking_female_tied[:10]:
            print(f"{item['rank']:>3} {item['player'].get('name','?')} - {item['score']} pts")

    simulation_info = [
        ['Simulación', datetime.now().strftime('%d/%m/%Y %H:%M:%S')],
        ['Jugador analizado', args.player],
        ['Simulaciones', args.sims],
        ['Pruebas restantes', str(len(event_weights) if event_weights else args.remaining)],
        ['Archivo generado', str(output_path)]
    ]

    source_info = [[label, status] for label, status in source_notes]
    top10_general_rows = [[item['rank'], item['player'].get('name', '?'), str(item['score'])] for item in ranking_general_tied[:10]]
    top10_male_rows = [[item['rank'], item['player'].get('name', '?'), str(item['score'])] for item in ranking_male_tied[:10]] if ranking_male_tied else []
    top10_female_rows = [[item['rank'], item['player'].get('name', '?'), str(item['score'])] for item in ranking_female_tied[:10]] if ranking_female_tied else []

    all_players_rows = []
    for item in ranking_general_tied:
        k = item['key']
        v = item['player']
        gender = v.get('gender')
        placements = placements_by_gender.get(gender, {}).get(k, {})
        all_players_rows.append([
            item['rank'],
            v.get('name', '?'),
            v.get('license', ''),
            gender or '',
            str(v.get('current_best9', 0)),
            f"{placements.get('WIN', 0):.2f}%",
            f"{placements.get('TOP3', 0):.1f}%",
            f"{placements.get('TOP10', 0):.1f}%",
            f"{placements.get('TOP20', 0):.1f}%"
        ])

    male_players_rows = []
    for item in ranking_male_tied:
        k = item['key']
        v = item['player']
        placements = placements_by_gender.get('M', {}).get(k, {})
        male_players_rows.append([
            item['rank'],
            v.get('name', '?'),
            v.get('license', ''),
            v.get('gender', ''),
            str(v.get('current_best9', 0)),
            f"{placements.get('WIN', 0):.2f}%",
            f"{placements.get('TOP3', 0):.1f}%",
            f"{placements.get('TOP10', 0):.1f}%",
            f"{placements.get('TOP20', 0):.1f}%"
        ])

    female_players_rows = []
    for item in ranking_female_tied:
        k = item['key']
        v = item['player']
        placements = placements_by_gender.get('F', {}).get(k, {})
        female_players_rows.append([
            item['rank'],
            v.get('name', '?'),
            v.get('license', ''),
            v.get('gender', ''),
            str(v.get('current_best9', 0)),
            f"{placements.get('WIN', 0):.2f}%",
            f"{placements.get('TOP3', 0):.1f}%",
            f"{placements.get('TOP10', 0):.1f}%",
            f"{placements.get('TOP20', 0):.1f}%"
        ])

    sections = [
        render_html_section('Resumen de la simulación', render_html_table(['Campo', 'Valor'], simulation_info)),
        render_html_section('Origen de resultados opcionales', render_html_table(['Archivo', 'Estado'], source_info)),
        render_html_section('Resumen del jugador', render_html_table(['Campo', 'Valor'], [
            ['Jugador', current_name],
            ['Licencia', current_lic],
            ['Posición actual general', rank_pos_general],
            ['Posición en categoría', rank_pos_group],
            ['Puntos actuales', players_all[query_key]['current_best9']]
        ])),
        render_html_section(
            'Probabilidades de victoria (TOP 20)',
            '<p>PRE = Puntos Reemplazables Esperados, la mejora neta potencial dentro de los 9 mejores resultados.</p>'
            '<p>Eficiencia PRE = TOP3 % / PRE medio; revela qué jugadores tienen más probabilidad de podio por punto de potencial restante.</p>'
            + render_html_table(
                ['Jugador', 'Win %', 'TOP3 %', 'TOP10 %', 'TOP20 %', 'PRE medio', 'PRE P90', 'Eficiencia PRE', 'Actual + PRE P90', '9ª mejor', 'Huecos'],
                top_win_rows
            )
        ),
        render_html_section('Puntos finales predichos para candidatos', render_html_table(['Jugador', 'Media', 'Mediana', 'SD', 'P10', 'P90'], points_projection_rows)),
        render_html_section(f'Estadísticas de {current_name}', render_html_table(['Categoría', 'Probabilidad'], query_stats_rows)),
    ]

    if distribution_rows:
        sections.append(render_html_section('Distribución de puntos finales', render_html_table(['Métrica', 'Valor'], distribution_rows)))
    if cutoff_rows:
        sections.append(render_html_section('Cortes estimados al final del circuito', render_html_table(['Corte', 'Media', 'Mediana', 'SD', 'P10', 'P90'], cutoff_rows)))

    sections.append(render_html_section('Top 10 actual general tras sumar la última prueba', render_html_table(['Pos.', 'Jugador', 'Puntos'], top10_general_rows)))
    if top10_male_rows:
        sections.append(render_html_section('Top 10 masculino actual', render_html_table(['Pos.', 'Jugador', 'Puntos'], top10_male_rows)))
    if top10_female_rows:
        sections.append(render_html_section('Top 10 femenino actual', render_html_table(['Pos.', 'Jugador', 'Puntos'], top10_female_rows)))
    sections.append(render_html_section('Todos los jugadores', render_html_table(['Pos.', 'Jugador', 'Licencia', 'Sexo', 'Puntos actuales', 'Win %', 'TOP3 %', 'TOP10 %', 'TOP20 %'], all_players_rows)))
    if male_players_rows:
        sections.append(render_html_section('Todos los jugadores masculinos', render_html_table(['Pos.', 'Jugador', 'Licencia', 'Sexo', 'Puntos actuales', 'Win %', 'TOP3 %', 'TOP10 %', 'TOP20 %'], male_players_rows)))
    if female_players_rows:
        sections.append(render_html_section('Todas las jugadoras', render_html_table(['Pos.', 'Jugador', 'Licencia', 'Sexo', 'Puntos actuales', 'Win %', 'TOP3 %', 'TOP10 %', 'TOP20 %'], female_players_rows)))

    export_to_html(str(output_path), f'Resultados de {current_name}', sections)

    print(f'\n✓ Resultados guardados en: {output_path}')


if __name__ == '__main__':
    main()
