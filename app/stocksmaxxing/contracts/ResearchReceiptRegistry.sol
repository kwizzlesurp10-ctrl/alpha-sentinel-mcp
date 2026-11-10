// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Minimal onchain anchor for Alpha Sentinel Proof-of-Research receipts (research only).
contract ResearchReceiptRegistry {
    event ResearchSealed(
        bytes32 indexed contentHash,
        bytes32 indexed briefId,
        address indexed sealer,
        uint256 sealedAt
    );

    mapping(bytes32 => uint256) public sealedAt;

    function seal(bytes32 contentHash, bytes32 briefId) external {
        require(sealedAt[contentHash] == 0, "already_sealed");
        uint256 ts = block.timestamp;
        sealedAt[contentHash] = ts;
        emit ResearchSealed(contentHash, briefId, msg.sender, ts);
    }
}
