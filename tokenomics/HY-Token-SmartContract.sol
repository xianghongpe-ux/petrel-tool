// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title 海燕党 · HY Token
/// @notice 治理与激励Token
/// @dev 政党名称：海燕党 | 英文名称：PETREL AI PARTY | 创始人：刘海燕（LIU HAIYAN）
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Permit.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/governance/utils/Votes.sol";

contract HYToken is ERC20, ERC20Permit, Ownable {
    uint256 public constant MAX_SUPPLY = 100_000_000 ether;
    uint256 public constant COMMUNITY_SHARE = 50_000_000 ether;
    uint256 public constant TEAM_SHARE = 20_000_000 ether;
    uint256 public constant TREASURY_SHARE = 20_000_000 ether;
    uint256 public constant ECOSYSTEM_SHARE = 10_000_000 ether;

    address public communityVault;
    address public teamVault;
    address public treasuryVault;
    address public ecosystemVault;

    bool public initialized;

    // 创世铭文
    string public constant GENESIS_NAME = "PETREL AI PARTY";
    string public constant FOUNDER = "LIU HAIYAN";

    event VaultsSet(
        address communityVault,
        address teamVault,
        address treasuryVault,
        address ecosystemVault
    );

    constructor()
        ERC20("HY Token", "HY")
        ERC20Permit("HY Token")
        Ownable(msg.sender)
    {}

    function initializeVaults(
        address _community,
        address _team,
        address _treasury,
        address _ecosystem
    ) external onlyOwner {
        require(!initialized, "already initialized");
        require(
            _community != address(0) &&
                _team != address(0) &&
                _treasury != address(0) &&
                _ecosystem != address(0),
            "invalid addresses"
        );
        initialized = true;
        communityVault = _community;
        teamVault = _team;
        treasuryVault = _treasury;
        ecosystemVault = _ecosystem;

        _mint(_community, COMMUNITY_SHARE);
        _mint(_team, TEAM_SHARE);
        _mint(_treasury, TREASURY_SHARE);
        _mint(_ecosystem, ECOSYSTEM_SHARE);

        emit VaultsSet(_community, _team, _treasury, _ecosystem);
    }

    function maxSupply() external pure returns (uint256) {
        return MAX_SUPPLY;
    }
}
