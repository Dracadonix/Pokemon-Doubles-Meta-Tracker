#!/usr/bin/env python3
"""
Pokémon Doubles Meta Tracker
Competitive Pokémon doubles battle tool that scrapes Smogon and other sources
Updates knowledge base hourly
"""

import os
import json
import time
import schedule
import logging
from datetime import datetime
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pokemon_tracker.log'),
        logging.StreamHandler()
    ]
)

class PokemonMetaTracker:
    def __init__(self, data_dir="meta_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.knowledge_base = {}
        self.sources = {
            'smogon': 'https://www.smogon.com/stats/',
            'pikalytics': 'https://pikalytics.com/',
            'pokemon_showdown': 'https://pokemonshowdown.com/ladders/',
            'vgc_pastes': 'https://www.smogon.com/forums/forums/vgc.577/'
        }
        
    def setup_directories(self):
        """Create necessary directories for data storage"""
        subdirs = ['smogon_data', 'usage_stats', 'teams', 'movesets', 'cache', 'history']
        for subdir in subdirs:
            (self.data_dir / subdir).mkdir(exist_ok=True)
        logging.info("Directories setup complete")
    
    def scrape_smogon_stats(self, format_name="gen9vgc2023doubles"):
        """Scrape usage statistics from Smogon"""
        try:
            url = f"{self.sources['smogon']}{format_name}/"
            logging.info(f"Scraping Smogon data from {url}")
            response = requests.get(url, timeout=30)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find the latest month's data
            links = soup.find_all('a')
            data_files = [link.get('href') for link in links 
                         if link.get('href') and 'txt' in link.get('href')]
            
            if data_files:
                latest_data = max(data_files)
                data_url = url + latest_data
                data_response = requests.get(data_url, timeout=30)
                
                pokemon_stats = self.parse_smogon_stats(data_response.text)
                self.save_data('smogon_stats', pokemon_stats)
                logging.info(f"Successfully scraped Smogon stats from {latest_data}")
                return pokemon_stats
            else:
                logging.warning("No data files found on Smogon")
                return None
                
        except Exception as e:
            logging.error(f"Error scraping Smogon: {e}")
            return None
    
    def parse_smogon_stats(self, stats_text):
        """Parse Smogon usage statistics text"""
        pokemon_data = {}
        lines = stats_text.split('\n')
        
        for line in lines:
            if '|' in line and not line.startswith('Total') and '----' not in line:
                parts = line.split('|')
                if len(parts) >= 4:
                    try:
                        pokemon = parts[2].strip()
                        usage_percent = parts[3].strip()
                        if '%' in usage_percent and pokemon and pokemon != 'Pokemon':
                            pokemon_data[pokemon] = {
                                'usage_percentage': float(usage_percent.replace('%', '')),
                                'raw_usage': parts[1].strip() if len(parts) > 1 else '0',
                                'last_updated': datetime.now().isoformat()
                            }
                    except (ValueError, IndexError) as e:
                        continue
        
        logging.info(f"Parsed {len(pokemon_data)} Pokémon from Smogon")
        return pokemon_data
    
    def scrape_pikalytics(self, pokemon_name):
        """Scrape usage and move data from Pikalytics"""
        try:
            url = f"{self.sources['pikalytics']}/vgc/{pokemon_name.lower().replace(' ', '-')}"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(url, headers=headers, timeout=30)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract move usage - adjust selectors based on actual Pikalytics structure
            moves = {}
            # This is a simplified example; you'll need to inspect Pikalytics's actual HTML
            move_elements = soup.find_all('div', class_='move-item')
            for move in move_elements[:10]:  # Top 10 moves
                name_elem = move.find('div', class_='move-name')
                percent_elem = move.find('div', class_='usage-percent')
                if name_elem and percent_elem:
                    moves[name_elem.text.strip()] = percent_elem.text.strip()
            
            pokemon_data = {
                'pokemon': pokemon_name,
                'moves': moves,
                'timestamp': datetime.now().isoformat()
            }
            
            self.save_data(f'pikalytics_{pokemon_name.lower()}', pokemon_data)
            logging.info(f"Scraped Pikalytics data for {pokemon_name}")
            return pokemon_data
            
        except Exception as e:
            logging.error(f"Error scraping Pikalytics for {pokemon_name}: {e}")
            return None
    
    def fetch_showdown_stats(self):
        """Fetch real-time usage stats from Pokémon Showdown"""
        try:
            # Showdown's ladder stats endpoint
            formats = ['gen9vgc2023doubles', 'gen9vgc2024regulationf']
            all_stats = {}
            
            for format_name in formats:
                url = f"{self.sources['pokemon_showdown']}{format_name}.json"
                response = requests.get(url, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    all_stats[format_name] = data
                    logging.info(f"Successfully fetched Showdown stats for {format_name}")
                else:
                    logging.warning(f"Failed to fetch {format_name} stats")
                
                time.sleep(1)  # Rate limiting
            
            if all_stats:
                self.save_data('showdown_stats', all_stats)
                return all_stats
            return None
                
        except Exception as e:
            logging.error(f"Error fetching Showdown stats: {e}")
            return None
    
    def scrape_team_pastes(self):
        """Scrape team pastebins from Smogon forums"""
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(self.sources['vgc_pastes'], headers=headers, timeout=30)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            teams = []
            # Find team paste links
            for link in soup.find_all('a', href=True):
                href = link['href']
                if any(domain in href for domain in ['pastebin.com', 'pokepast.es', 'porygon.co']):
                    teams.append({
                        'url': href,
                        'title': link.text.strip()[:100],  # Limit title length
                        'scraped_at': datetime.now().isoformat()
                    })
            
            # Remove duplicates
            unique_teams = []
            seen_urls = set()
            for team in teams:
                if team['url'] not in seen_urls:
                    seen_urls.add(team['url'])
                    unique_teams.append(team)
            
            self.save_data('team_pastes', unique_teams[:100])  # Save latest 100 teams
            logging.info(f"Scraped {len(unique_teams)} unique team pastes")
            return unique_teams
            
        except Exception as e:
            logging.error(f"Error scraping team pastes: {e}")
            return None
    
    def save_data(self, key, data):
        """Save data to JSON file"""
        file_path = self.data_dir / f"{key}.json"
        try:
            # Add metadata
            save_data = {
                'data': data,
                'metadata': {
                    'saved_at': datetime.now().isoformat(),
                    'source': key.split('_')[0] if '_' in key else 'unknown'
                }
            }
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            logging.info(f"Saved {key} data to {file_path}")
            return True
        except Exception as e:
            logging.error(f"Error saving {key} data: {e}")
            return False
    
    def load_data(self, key):
        """Load data from JSON file"""
        file_path = self.data_dir / f"{key}.json"
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    saved_data = json.load(f)
                    return saved_data.get('data', saved_data)  # Handle both formats
        except Exception as e:
            logging.error(f"Error loading {key} data: {e}")
        return None
    
    def get_top_pokemon(self, limit=20):
        """Get top Pokémon by usage from Smogon stats"""
        stats = self.load_data('smogon_stats')
        if stats:
            sorted_pokemon = sorted(stats.items(), 
                                  key=lambda x: x[1].get('usage_percentage', 0), 
                                  reverse=True)
            return sorted_pokemon[:limit]
        return []
    
    def get_pokemon_details(self, pokemon_name):
        """Get comprehensive details for a specific Pokémon"""
        details = {
            'name': pokemon_name,
            'usage_stats': None,
            'moves': None,
            'teams_using': [],
            'last_checked': datetime.now().isoformat()
        }
        
        # Get usage stats
        stats = self.load_data('smogon_stats')
        if stats and pokemon_name in stats:
            details['usage_stats'] = stats[pokemon_name]
        
        # Get move data
        pikalytics_data = self.load_data(f'pikalytics_{pokemon_name.lower()}')
        if pikalytics_data:
            details['moves'] = pikalytics_data.get('moves', {})
        
        return details
    
    def search_pokemon(self, query):
        """Search for Pokémon in the knowledge base"""
        query = query.lower()
        stats = self.load_data('smogon_stats')
        
        if not stats:
            return []
        
        results = []
        for pokemon, data in stats.items():
            if query in pokemon.lower():
                results.append({
                    'name': pokemon,
                    'usage': data.get('usage_percentage', 0),
                    'raw_usage': data.get('raw_usage', '0')
                })
        
        return sorted(results, key=lambda x: x['usage'], reverse=True)
    
    def get_team_recommendations(self, core_pokemon):
        """Get team recommendations based on core Pokémon"""
        teams = self.load_data('team_pastes')
        if not teams:
            return []
        
        recommendations = []
        core_pokemon_lower = core_pokemon.lower()
        for team in teams:
            if core_pokemon_lower in team.get('title', '').lower():
                recommendations.append(team)
        
        return recommendations[:10]  # Return top 10 matches
    
    def update_all_data(self):
        """Update all data sources"""
        start_time = time.time()
        logging.info("=" * 50)
        logging.info("Starting hourly data update...")
        
        # Track what was updated
        updates = {
            'timestamp': datetime.now().isoformat(),
            'sources': {}
        }
        
        # Update from Smogon
        smogon_data = self.scrape_smogon_stats()
        updates['sources']['smogon'] = 'success' if smogon_data else 'failed'
        
        # Update from Showdown
        showdown_data = self.fetch_showdown_stats()
        updates['sources']['showdown'] = 'success' if showdown_data else 'failed'
        
        # Update team pastes
        teams_data = self.scrape_team_pastes()
        updates['sources']['teams'] = 'success' if teams_data else 'failed'
        
        # Update top 20 Pokémon from Pikalytics
        top_pokemon = self.get_top_pokemon(20)
        pika_success = 0
        for pokemon, _ in top_pokemon:
            if self.scrape_pikalytics(pokemon):
                pika_success += 1
            time.sleep(0.5)  # Rate limiting
        
        updates['sources']['pikalytics'] = f'{pika_success}/20 successful'
        
        # Save update history
        history = self.load_data('update_history') or []
        history.append(updates)
        # Keep last 100 updates
        if len(history) > 100:
            history = history[-100:]
        self.save_data('update_history', history)
        
        # Save last update timestamp
        self.save_data('last_update', {
            'timestamp': datetime.now().isoformat(),
            'duration_seconds': round(time.time() - start_time, 2),
            'sources_updated': updates['sources']
        })
        
        logging.info(f"Hourly data update completed in {updates['duration_seconds']} seconds")
        logging.info("=" * 50)
    
    def print_summary(self):
        """Print a summary of the current data"""
        print("\n" + "="*50)
        print("POKÉMON DOUBLES META TRACKER - CURRENT STATUS")
        print("="*50)
        
        last_update = self.load_data('last_update')
        if last_update:
            print(f"Last Update: {last_update.get('timestamp', 'Unknown')}")
            print(f"Update Duration: {last_update.get('duration_seconds', 'N/A')} seconds")
        
        stats = self.load_data('smogon_stats')
        if stats:
            print(f"\nPokémon in Database: {len(stats)}")
            top_5 = self.get_top_pokemon(5)
            print("\nTop 5 Pokémon by Usage:")
            for i, (pokemon, data) in enumerate(top_5, 1):
                print(f"  {i}. {pokemon}: {data['usage_percentage']:.1f}%")
        
        teams = self.load_data('team_pastes')
        if teams:
            print(f"\nTeams Collected: {len(teams)}")
        
        history = self.load_data('update_history')
        if history:
            print(f"\nTotal Updates Performed: {len(history)}")
        
        print("="*50)

def main():
    """Main function to run the tool"""
    print("\n" + "="*60)
    print("   POKÉMON DOUBLES META TRACKER v1.0")
    print("   Real-time metagame analysis tool")
    print("="*60)
    
    tracker = PokemonMetaTracker()
    tracker.setup_directories()
    
    print("\n[1/3] Performing initial data download...")
    print("      This may take 2-3 minutes...")
    tracker.update_all_data()
    
    print("\n[2/3] Loading data into memory...")
    tracker.print_summary()
    
    print("\n[3/3] Ready for commands!")
    
    print("\n" + "="*60)
    print("COMMANDS:")
    print("  • top [number]     - Show top Pokémon (default: 20)")
    print("  • search <name>    - Search for a Pokémon")
    print("  • details <name>   - Get detailed Pokémon info")
    print("  • team <pokemon>   - Find teams with specific Pokémon")
    print("  • summary          - Show data summary")
    print("  • update           - Force manual update")
    print("  • exit             - Exit the tool")
    print("="*60)
    print("\n✨ Data will automatically update every hour in the background\n")
    
    # Start scheduler in background thread
    import threading
    def run_scheduler():
        schedule.every().hour.do(tracker.update_all_data)
        while True:
            schedule.run_pending()
            time.sleep(60)
    
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Interactive CLI
    while True:
        try:
            command = input("🐾 ").strip().lower()
            
            if command == 'exit':
                print("\nThank you for using Pokémon Doubles Meta Tracker!")
                print("Goodbye! 👋\n")
                break
            
            elif command == 'summary':
                tracker.print_summary()
            
            elif command.startswith('top'):
                parts = command.split()
                limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 20
                top = tracker.get_top_pokemon(limit)
                if top:
                    print(f"\n📊 Top {limit} Pokémon by Usage:")
                    print("-" * 40)
                    for i, (pokemon, data) in enumerate(top, 1):
                        bar_length = int(data['usage_percentage'] / 2)
                        bar = "█" * bar_length + "░" * (50 - bar_length)
                        print(f"{i:2}. {pokemon:<20} {data['usage_percentage']:5.1f}% {bar}")
                else:
                    print("No data available. Run 'update' first.")
            
            elif command.startswith('search '):
                query = command[7:]
                results = tracker.search_pokemon(query)
                if results:
                    print(f"\n🔍 Search results for '{query}':")
                    print("-" * 40)
                    for r in results[:15]:
                        print(f"  • {r['name']:<25} {r['usage']:5.1f}% usage")
                else:
                    print(f"No Pokémon found matching '{query}'")
            
            elif command.startswith('details '):
                pokemon = command[8:]
                details = tracker.get_pokemon_details(pokemon)
                print(f"\n📋 DETAILS: {pokemon.upper()}")
                print("-" * 40)
                if details['usage_stats']:
                    print(f"Usage Rate:     {details['usage_stats']['usage_percentage']:.1f}%")
                    print(f"Raw Usage:      {details['usage_stats'].get('raw_usage', 'N/A')}")
                    print(f"Last Updated:   {details['usage_stats'].get('last_updated', 'N/A')[:19]}")
                else:
                    print("Usage Data:     Not available")
                
                if details['moves']:
                    print("\nCommon Moves:")
                    for move, usage in list(details['moves'].items())[:8]:
                        print(f"  • {move:<20} {usage}")
                else:
                    print("\nMove Data:      Not available")
            
            elif command.startswith('team '):
                pokemon = command[5:]
                teams = tracker.get_team_recommendations(pokemon)
                if teams:
                    print(f"\n👥 Teams featuring {pokemon.upper()}:")
                    print("-" * 40)
                    for i, team in enumerate(teams[:5], 1):
                        print(f"{i}. {team['title'][:50]}")
                        print(f"   URL: {team['url']}")
                        print()
                else:
                    print(f"No teams found featuring '{pokemon}'")
            
            elif command == 'update':
                print("\n🔄 Forcing manual update...")
                tracker.update_all_data()
                print("✅ Update completed successfully!")
                tracker.print_summary()
            
            else:
                print("❓ Unknown command. Type 'top', 'search <name>', 'details <name>', 'team <pokemon>', 'summary', 'update', or 'exit'")
        
        except KeyboardInterrupt:
            print("\n\nInterrupted by user. Goodbye!")
            break
        except Exception as e:
            logging.error(f"Error processing command: {e}")
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    # Check and install required packages
    required_packages = ['requests', 'beautifulsoup4', 'schedule']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"Installing missing packages: {', '.join(missing_packages)}")
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing_packages)
        print("Packages installed successfully!\n")
    
    main()
